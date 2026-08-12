"""Render structured CoachResponse as coach-facing markdown."""

from __future__ import annotations

import re

from music_coach_ami.types import CoachResponse

# Bare bold headers (no trailing label colon like **Dbmaj7:**).
_SECTION_HEADERS = frozenset(
    {
        "**Practice**",
        "**Listen for**",
        "**How to play it**",
        "**Bass line**",
        "**What to do**",
        "**What to listen for**",
        "**When to progress**",
        "**Steps in the app**",
    }
)


def _is_bare_bold_header(s: str) -> bool:
    if s in _SECTION_HEADERS:
        return True
    if re.fullmatch(r"\*\*[^*]+\*\*", s):
        return True
    # e.g. **Bass line** — read the staff notation below.
    if s.startswith("**") and "—" in s and not re.match(r"^\*\*[^*]+:\*\*", s):
        return True
    return False


def _is_bold_label_line(s: str) -> bool:
    """Bold chord/label lines such as **Dbmaj7:** Db · F · …"""
    return bool(re.match(r"^\*\*[^*]+:\*\*", s))


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
            if not s:
                continue
            # Strip accidental leading list markers before classifying.
            bare = re.sub(r"^[-*]\s+", "", s)
            if bare.startswith("#") or _is_bare_bold_header(bare):
                parts.append(bare)
                continue
            if _is_bold_label_line(bare):
                parts.append(f"- {bare}")
                continue
            if s.startswith(("- ", "* ")) or re.match(r"^\d+\.\s", s):
                # Already a list item — do not double-prefix.
                parts.append(s)
                continue
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
            s = step.strip()
            if s in ("**Then:**", "**Use:**", "**Go to:**") or s.startswith("**") and s.endswith(":**"):
                parts.append(s)
            elif re.match(r"^\d+\.\s", s):
                parts.append(s)
            else:
                parts.append(f"- {s}")
    if response.suggested_next_action:
        parts.append(f"**Next:** {response.suggested_next_action.strip()}")
    return "\n\n".join(p for p in parts if p)
