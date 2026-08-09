"""Hybrid testable intent router — rules first, legacy AMI hooks for edge cases."""

from __future__ import annotations

import re
from typing import Any

from music_coach_ami.app_knowledge import feature_by_question
from music_coach_ami.context_reader import read_coach_context
from music_coach_ami.entities import (
    extract_constraints,
    extract_entities,
    normalize_question,
    parse_duration_minutes,
)
from music_coach_ami.types import CoachIntent, CoachRequest


def _legacy_intent_for(coach_intent: CoachIntent) -> str:
    mapping = {
        CoachIntent.PRACTICE_PLAN: "practice_plan",
        CoachIntent.TECHNIQUE_PROBLEM: "skill_technique",
        CoachIntent.IMPROVISATION_COACHING: "improvisation_coaching",
        CoachIntent.REPERTOIRE_RECOMMENDATION: "similar_songs",
        CoachIntent.APP_NAVIGATION: "app_navigation",
        CoachIntent.FEATURE_EXPLANATION: "feature_explanation",
        CoachIntent.CREATIVE_FEATURE_HELP: "creative_feature_help",
        CoachIntent.APP_FEATURE_RECOMMENDATION: "app_feature_recommendation",
        CoachIntent.THEORY_EXPLANATION: "music_theory",
        CoachIntent.SCALE_PRACTICE: "scale_practice",
        CoachIntent.SONG_COACHING: "section_focus",
        CoachIntent.PRACTICE_HISTORY_ANALYSIS: "practice_history_analysis",
        CoachIntent.MUSIC_TRANSPOSITION: "music_transposition",
        CoachIntent.FALLBACK: "music_general",
    }
    return mapping.get(coach_intent, "music_general")


def _rule_route(normalized: str, coach_page: str) -> tuple[CoachIntent, float]:
    low = normalized.lower()
    page = str(coach_page or "").lower()

    if any(
        p in low
        for p in (
            "analyze my practice",
            "practice history analysis",
            "patterns in my practice",
        )
    ):
        return CoachIntent.PRACTICE_HISTORY_ANALYSIS, 0.92

    if any(
        p in low
        for p in (
            "how can i practice improvising",
            "practice improvising on this song",
            "improvise on this song",
            "improvising over the current chord",
            "improvising over the current progression",
        )
    ):
        return CoachIntent.IMPROVISATION_COACHING, 0.91

    if "what part of the app" in low and any(p in low for p in ("scale", "chord", "theory", "harmony")):
        return CoachIntent.APP_FEATURE_RECOMMENDATION, 0.88

    if "difference between" in low and "backing" in low and "jam" in low:
        return CoachIntent.FEATURE_EXPLANATION, 0.9

    if "difference between" in low and "mission" in low and "live coach" in low:
        return CoachIntent.FEATURE_EXPLANATION, 0.9

    if re.search(r"\bwhere (?:do i|can i)\b", low) or re.search(r"\bhow do i (log|save|upload|create|change|find)\b", low):
        if feature_by_question(low) or "log" in low or "upload" in low or "backing" in low:
            return CoachIntent.APP_NAVIGATION, 0.9

    if "difference between" in low and ("mission" in low or "jam session" in low):
        return CoachIntent.CREATIVE_FEATURE_HELP, 0.93

    if any(p in low for p in ("what is creative", "what are missions", "what is the jam session", "what is style jam")):
        return CoachIntent.CREATIVE_FEATURE_HELP, 0.88

    if any(p in low for p in ("what does", "what is a backing", "what is live coach", "what is harmony map")):
        if "backing" in low or "practice log" in low or "upload" in low or "live coach" in low or "harmony map" in low:
            return CoachIntent.FEATURE_EXPLANATION, 0.86
        if "motif" in low or "improvisation" in low and "what is" in low:
            return CoachIntent.THEORY_EXPLANATION if "ii-v" in low or "dorian" in low else CoachIntent.CREATIVE_FEATURE_HELP

    if any(
        p in low
        for p in (
            "where should i go",
            "which feature",
            "which part of the app",
            "just want to jam",
            "structured improvisation",
            "record myself and get feedback",
            "track what i practiced",
        )
    ):
        return CoachIntent.APP_FEATURE_RECOMMENDATION, 0.87

    if any(p in low for p in ("what is a ii-v-i", "what is dorian", "what is a chord tone", "what is syncopation", "what is phrasing", "what does transposition mean")):
        return CoachIntent.THEORY_EXPLANATION, 0.85

    if "what is a major scale" in low or "what is a minor scale" in low:
        return CoachIntent.THEORY_EXPLANATION, 0.86
    if re.search(r"\bwhat is .+\bscale\b", low) and not re.search(r"\b(show me|give me|write)\b", low):
        return CoachIntent.THEORY_EXPLANATION, 0.84

    if re.search(r"\bwhat scales should i practice\b", low):
        return CoachIntent.SCALE_PRACTICE, 0.88

    if re.search(r"\bwhat is\b", low) and re.search(r"\bscale\b", low):
        if not re.search(r"\b(show me|give me|write)\b", low):
            return CoachIntent.THEORY_EXPLANATION, 0.84

    if re.search(r"\b(show me|give me|write)\b", low) and re.search(
        r"\b("
        r"major|minor|harmonic minor|melodic minor|natural minor|"
        r"pentatonic|blues|dorian|mixolydian|lydian|locrian"
        r")\b",
        low,
    ):
        return CoachIntent.SCALE_PRACTICE, 0.9

    if re.search(r"\b(show me|give me|write)\b", low) and any(
        p in low
        for p in (
            "scale",
            "in thirds",
            "in fourths",
            "in fifths",
            "in sixths",
            "in sevenths",
            "interval exercise",
            "sheet music",
            "harmonic minor",
            "melodic minor",
            " pentatonic",
            " blues",
        )
    ):
        return CoachIntent.SCALE_PRACTICE, 0.9
    if "sheet music" in low and any(p in low for p in ("major", "minor", "scale", "thirds", "fourths")):
        return CoachIntent.SCALE_PRACTICE, 0.88

    if any(p in low for p in ("songs should i", "easy jazz songs", "songs good for", "recommend songs", "songs for learning improvisation", "what kind of songs")):
        return CoachIntent.REPERTOIRE_RECOMMENDATION, 0.84
    if "songs" in low and any(p in low for p in ("good for learning", "good for improvisation", "learning improvisation")):
        return CoachIntent.REPERTOIRE_RECOMMENDATION, 0.84

    if any(
        p in low
        for p in (
            "what is improvisation",
            "how do i improvise",
            "how do i start improvising",
            "less random",
            "develop a motif",
            "what should i play over",
            "what notes should i use over",
            "practice over this chord",
            "practice over the chord",
            "what should i practice over",
            "how should i practice a motif",
            "how should i practice developing a motif",
        )
    ):
        return CoachIntent.IMPROVISATION_COACHING, 0.86

    if re.search(r"\bwhat is a motif\b", low) or (re.search(r"\bwhat is\b", low) and "motif" in low and "creative" not in low):
        return CoachIntent.THEORY_EXPLANATION, 0.84

    if any(
        p in low
        for p in (
            "improve my tone",
            "tone sounds",
            "breath support",
            "articulation",
            "notes don't come out",
            "fuller sound",
            "transitions smoother",
        )
    ):
        return CoachIntent.TECHNIQUE_PROBLEM, 0.88

    if parse_duration_minutes(normalized) and any(
        p in low for p in ("practice", "routine", "plan", "today", "should i", "session")
    ):
        return CoachIntent.PRACTICE_PLAN, 0.9
    if re.search(r"\b\d{1,3}\s*[- ]?\s*minute", low) and any(
        p in low for p in ("practice", "routine", "plan", "today", "should i")
    ):
        return CoachIntent.PRACTICE_PLAN, 0.9
    if ("what should i practice" in low and "what kind of songs" not in low) or "practice plan" in low or "practice today" in low:
        if not any(p in low for p in ("over this chord", "over the chord", "chord progression", "progression?")):
            return CoachIntent.PRACTICE_PLAN, 0.88

    if any(p in low for p in ("which section", "work on in this song", "practice melody", "what tempo should i start")):
        return CoachIntent.SONG_COACHING, 0.82

    # Delegate remaining cases to existing music_ami_context classifier
    try:
        from music_ami_context import detect_music_send_intent

        legacy = detect_music_send_intent(normalized, page)
        legacy_map = {
            "practice_plan": CoachIntent.PRACTICE_PLAN,
            "skill_technique": CoachIntent.TECHNIQUE_PROBLEM,
            "similar_songs": CoachIntent.REPERTOIRE_RECOMMENDATION,
            "music_theory": CoachIntent.THEORY_EXPLANATION,
            "practice_history_analysis": CoachIntent.PRACTICE_HISTORY_ANALYSIS,
            "music_transposition": CoachIntent.MUSIC_TRANSPOSITION,
            "section_focus": CoachIntent.SONG_COACHING,
        }
        if legacy in legacy_map:
            return legacy_map[legacy], 0.75
    except ImportError:
        pass

    return CoachIntent.FALLBACK, 0.4


def route_question(
    question: str,
    session_state: dict[str, Any] | None = None,
    *,
    ami_ctx: dict[str, Any] | None = None,
) -> CoachRequest:
    session = session_state if isinstance(session_state, dict) else {}
    ctx = read_coach_context(session, ami_ctx=ami_ctx)
    normalized = normalize_question(question)
    entities = extract_entities(normalized, ctx.instrument)
    constraints = extract_constraints(normalized, entities)
    intent, confidence = _rule_route(normalized, ctx.coach_page)
    return CoachRequest(
        raw_question=str(question or ""),
        normalized_question=normalized,
        intent=intent,
        confidence=confidence,
        entities=entities,
        constraints=constraints,
        context=ctx,
        legacy_intent_hint=_legacy_intent_for(intent),
    )
