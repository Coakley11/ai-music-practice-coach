"""AMI Music Coach — routed requests, specialized solvers, read-only CoachContext."""

from music_coach_ami.pipeline import run_coach_pipeline
from music_coach_ami.router import CoachIntent, route_question
from music_coach_ami.types import CoachContext, CoachRequest, CoachResponse

__all__ = [
    "CoachContext",
    "CoachIntent",
    "CoachRequest",
    "CoachResponse",
    "route_question",
    "run_coach_pipeline",
]
