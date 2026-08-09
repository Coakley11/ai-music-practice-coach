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
        has_practice_header = any(str(s).strip() == "**Practice**" for s in response.practice_steps)
        if not has_practice_header:
            parts.append("**What to do**")
        for step in response.practice_steps:
            s = step.strip()
            if s.startswith("#") or s == "**Practice**" or s == "**Listen for**" or (
                s.startswith("**") and ":" in s
            ):
                parts.append(s)
            else:
                parts.append(f"- {s}")
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
    return "\n\n".join(p for p in parts if p)
