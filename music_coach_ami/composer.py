"""Render structured CoachResponse as coach-facing markdown."""

from __future__ import annotations

from music_coach_ami.types import CoachResponse


def compose_coach_markdown(response: CoachResponse) -> str:
    parts: list[str] = []
    if response.direct_answer:
        parts.append(response.direct_answer.strip())
    if response.explanation:
        parts.append(response.explanation.strip())
    if response.recommendation:
        parts.append(f"**Recommendation:** {response.recommendation.strip()}")
    if response.practice_steps:
        parts.append("**What to do**")
        for step in response.practice_steps:
            if step.strip().startswith("#"):
                parts.append(step.strip())
            else:
                parts.append(f"- {step}")
    if response.what_to_listen_for:
        parts.append("**What to listen for**")
        for item in response.what_to_listen_for:
            parts.append(f"- {item}")
    if response.progression_criteria:
        parts.append("**When to progress**")
        for item in response.progression_criteria:
            parts.append(f"- {item}")
    if response.app_navigation_steps:
        parts.append("**Steps in the app**")
        for step in response.app_navigation_steps:
            parts.append(f"- {step}")
    if response.suggested_next_action:
        parts.append(f"**Next:** {response.suggested_next_action.strip()}")
    if response.notation_abc:
        parts.append("**Sheet music (ABC)**")
        parts.append(f"```abc\n{response.notation_abc.strip()}\n```")
    return "\n\n".join(p for p in parts if p)
