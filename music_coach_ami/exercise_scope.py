"""AMI exercise requests: say what the chart can honestly support instead of quietly shrinking the request.

* A chart that cannot be tied to the song the app has active is never used to build an exercise.
* "over the verse" / "over the chorus" / "over the whole song" ask for more than the multi-chord engines build today
  (2- or 3-chord stretches). AMI names the real section and its progression, says what it can build, and offers exact phrasings;
  it does not hand back a one-chord substitute unless the player asked for one chord.
"""

from __future__ import annotations

import re
from typing import Any

_WHOLE_SONG_RE = re.compile(r"\b(?:whole|entire|full|complete)\s+(?:song|tune|chart|progression|form)\b|\bover\s+the\s+(?:song|tune|chart)\b", re.I)
_ONE_CHORD_RE = re.compile(r"\b(?:first|this|current|that|one|single|selected|a)\s+chord\b", re.I)
_SUPPORTED = "2 or 3 consecutive chords"


def _clean(value: object) -> str:
    return str(value or "").strip()


def collapse_loop(chords: list[str]) -> tuple[list[str], int]:
    """(unit, repeats): the shortest unit that, repeated exactly, makes ``chords`` (repeats == 1: no exact repetition)."""
    n = len(chords)
    for p in range(1, n // 2 + 1):
        if n % p == 0 and all(chords[i] == chords[i % p] for i in range(n)):
            return list(chords[:p]), n // p
    return list(chords), 1


def _pretty(chord: str) -> str:
    return re.sub(r"(?<=[A-G])b", "♭", chord).replace("#", "♯")


def _progression_line(full: list[str], charted: list[str]) -> str:
    """The section's progression in the player's chord names, with its true length: ``full`` is the whole chart section (it decides
    the count and whether it is one loop repeated), ``charted`` only supplies the names the player sees."""
    unit, times = collapse_loop(full)
    arrow = " → "
    names = charted[:len(unit)] if len(charted) >= len(unit) else unit
    if times > 1:
        return f"{arrow.join(_pretty(c) for c in names)}, repeated {times} times ({len(full)} chords in all)"
    shown = charted if len(charted) == len(full) else full
    shown = shown if len(shown) <= 16 else shown[:16]
    return arrow.join(_pretty(c) for c in shown) + (f" … ({len(full)} chords in all)" if len(full) > 16 else "")


def _what(intent: Any) -> str:
    technique = _clean(getattr(intent, "technique", "")).replace("_", " ")
    if technique:
        return {"enclosure": "an enclosure exercise", "chromatic approach": "a chromatic approach exercise",
                "bebop": "a bebop line", "target tone": "a target-tone line"}.get(technique, f"a {technique} exercise")
    vocab = _clean(getattr(intent, "vocabulary", "")).replace("_", "-")
    return f"a {vocab} exercise" if vocab else "an exercise"


def _payload(message: str, steps: list[str], intent: Any, diag: dict[str, Any]) -> dict[str, Any]:
    return {
        "direct_answer": message, "practice_steps": steps, "what_to_listen_for": [],
        "suggested_next_action": "Ask again with a stretch of 2 or 3 chords, or one chord.",
        "notation_abc": "", "notation_abc_sections": [],
        "diagnostics": {"musical_idea_content": True, "exercise_bridge": True, "exercise_failed": True, **diag,
                        "exercise_intent": intent.to_dict() if hasattr(intent, "to_dict") else {}},
    }


def _as_charted(session_ref: Any, chart: dict[str, Any]) -> dict[str, list[str]]:
    """The sections as the player's chart (and the Missions page) show them; AMI's own chart keeps the fullest chord qualities."""
    try:
        from improvisation_intelligence_ui import _mission_improv_ctx_from_session
        from improvisation_motif import resolve_improv_section_rows
        from music_coach_ami.session_access import as_mutable_session

        probe = dict(as_mutable_session(session_ref) or {})
        probe["improv_intelligence_tab"] = "Missions"
        probe["creative_improv_intelligence_tab"] = "Missions"
        ctx = _mission_improv_ctx_from_session(probe)
        rows = resolve_improv_section_rows(probe, ctx) if ctx is not None else []
        out = {str(label): [str(c) for c in clean] for label, clean, _raw in rows if clean}
        if out:
            return out
    except Exception:
        pass
    sections = chart.get("chart_sections") if isinstance(chart.get("chart_sections"), dict) else {}
    return {str(k): [str(c) for c in v] for k, v in sections.items()}


def _say_name(name: str) -> str:
    return re.sub(r"\s*\d+$", "", name).strip().lower()


def exercise_scope_guard(
    question: str, intent: Any, chart: dict[str, Any], section_resolve: dict[str, Any], session_ref: Any = None
) -> dict[str, Any] | None:
    """A payload that answers honestly instead of building, or None when the request can go ahead."""
    named_chord = bool(_clean(getattr(intent, "explicit_chord", "")) or getattr(intent, "span_chords", ()))
    if chart.get("chart_verified") is False and not named_chord:
        reason = _clean(chart.get("chart_unverified_reason")) or "the chart could not be tied to the active song"
        return _payload(
            f"I can't build this against the song's chords, because {reason}, and I won't guess with another song's chords. "
            + ("Add chords in the Custom Progression Lab, select the song again" if "no chords" in reason else "Select the song again")
            + ", or name a chord (for example \"over Fm7\").",
            ["Your song, Practice Key and chart are unchanged."], intent,
            {"exercise_failure_reason": "chart_unverified", "chart_unverified_reason": reason, "chart_live_source": chart.get("live_source")},
        )
    if getattr(intent, "span_length", 0) or getattr(intent, "span_chords", ()) or _ONE_CHORD_RE.search(question or ""):
        return None
    whole = bool(_WHOLE_SONG_RE.search(question or ""))
    sectional = getattr(intent, "scope", "") == "section"
    if not (whole or sectional):
        return None
    what = _what(intent)
    sections = _as_charted(session_ref, chart)
    if whole:
        full_secs = chart.get("chart_sections") if isinstance(chart.get("chart_sections"), dict) else {}
        counts = {name: len(full_secs.get(name) or ch) for name, ch in sections.items()}
        listing = "; ".join(f"**{name}** ({n} chords)" for name, n in counts.items()) or "no sections are available"
        message = (
            f"You asked for {what} over the whole song. The chart has {listing}. I can build {what} across {_SUPPORTED} at a time, "
            "not across a whole song yet, and I won't quietly cover only part of it."
        )
        first = _say_name(next(iter(sections), ""))
    else:
        name = _clean(section_resolve.get("section")) or _clean(chart.get("active_section"))
        charted = [c for c in (sections.get(name) or []) if _clean(c)]
        chart_secs = chart.get("chart_sections") if isinstance(chart.get("chart_sections"), dict) else {}
        chords = [c for c in (chart_secs.get(name) or section_resolve.get("chords") or charted) if _clean(c)]
        if not chords:
            return None
        message = (
            f"You asked for {what} over the **{name}**. It is {_progression_line(chords, charted)}. I can build {what} across {_SUPPORTED} at a "
            f"time, not across all {len(chords)} chords of a section yet, so I haven't built a one-chord version without asking."
        )
        first = _say_name(name)
    label = first or "section"
    steps = [
        f"For two chords: \"Give me {what} over the first two chords of the {label}\".",
        f"For three chords: \"Give me {what} over the first three chords of the {label}\".",
        "For one chord, say so: \"over the first chord\" (or name a chord, for example \"over G7\").",
    ]
    return _payload(message, steps, intent, {"exercise_failure_reason": "section_scope_not_supported_yet", "requested_scope": "song" if whole else "section",
                                              "supported_span_lengths": [2, 3]})
