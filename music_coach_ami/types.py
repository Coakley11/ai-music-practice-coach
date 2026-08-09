"""Structured coach request/response and read-only context."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CoachIntent(str, Enum):
    PRACTICE_PLAN = "practice_plan"
    TECHNIQUE_PROBLEM = "technique_problem"
    IMPROVISATION_COACHING = "improvisation_coaching"
    REPERTOIRE_RECOMMENDATION = "repertoire_recommendation"
    APP_NAVIGATION = "app_navigation"
    FEATURE_EXPLANATION = "feature_explanation"
    CREATIVE_FEATURE_HELP = "creative_feature_help"
    APP_FEATURE_RECOMMENDATION = "app_feature_recommendation"
    THEORY_EXPLANATION = "theory_explanation"
    SCALE_PRACTICE = "scale_practice"
    SONG_COACHING = "song_coaching"
    PRACTICE_HISTORY_ANALYSIS = "practice_history_analysis"
    MUSIC_TRANSPOSITION = "music_transposition"
    FALLBACK = "music_general"


@dataclass(frozen=True)
class CoachContext:
    """Read-only snapshot — AMI must not mutate app musical state."""

    instrument: str = ""
    level: str = ""
    practice_focus: str = ""
    available_practice_minutes: int | None = None
    active_song_title: str = ""
    active_song_pick_key: str = ""
    song_original_key: str = ""
    current_practice_key: str = ""
    active_section: str = ""
    current_chord: str = ""
    progression_summary: str = ""
    tempo_bpm: int | None = None
    active_mission: str = ""
    creative_mode: str = ""
    creative_tab: str = ""
    studio_page: str = ""
    coach_page: str = ""
    recent_practice_evidence: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedEntities:
    instrument: str = ""
    skill_topic: str = ""
    feature_id: str = ""
    style_genre: str = ""
    theory_topic: str = ""
    section_name: str = ""
    song_title: str = ""


@dataclass
class CoachConstraints:
    requested_duration_minutes: int | None = None
    tone_focus: bool = False
    improvisation_focus: bool = False


@dataclass
class CoachRequest:
    raw_question: str
    normalized_question: str
    intent: CoachIntent
    confidence: float
    entities: ExtractedEntities
    constraints: CoachConstraints
    context: CoachContext
    legacy_intent_hint: str = ""
    follow_up_ref: str = ""


@dataclass
class CoachResponse:
    intent: CoachIntent
    direct_answer: str = ""
    recommendation: str = ""
    practice_steps: list[str] = field(default_factory=list)
    what_to_listen_for: list[str] = field(default_factory=list)
    progression_criteria: list[str] = field(default_factory=list)
    app_navigation_steps: list[str] = field(default_factory=list)
    explanation: str = ""
    suggested_next_action: str = ""
    source_solver: str = ""
    notation_abc: str = ""
    notation_abc_sections: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def composed_markdown(self) -> str:
        from music_coach_ami.composer import compose_coach_markdown

        return compose_coach_markdown(self)
