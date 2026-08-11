"""Personalized practice-plan composition — instrument, level, focus, Practice Log."""

from __future__ import annotations

import re
from typing import Any

from music_coach_ami.practice_history_context import PracticeHistorySnapshot, snapshot_from_coach_context
from music_coach_ami.types import CoachRequest
from music_coach_instrument_voice import instrument_family, tone_focused_practice_plan


def _minutes(req: CoachRequest) -> int:
    if req.constraints.requested_duration_minutes:
        return req.constraints.requested_duration_minutes
    if req.context.available_practice_minutes:
        return max(15, min(90, int(req.context.available_practice_minutes)))
    return 30


def _allocate(total: int, weights: dict[str, float]) -> dict[str, int]:
    if not weights:
        return {}
    norm = sum(max(0.0, float(v)) for v in weights.values()) or 1.0
    raw = {k: total * max(0.0, float(v)) / norm for k, v in weights.items()}
    rounded = {k: int(v) for k, v in raw.items()}
    remainder = total - sum(rounded.values())
    keys = list(raw.keys())
    i = 0
    while remainder > 0 and keys:
        rounded[keys[i % len(keys)]] += 1
        remainder -= 1
        i += 1
    return rounded


def _focus_bucket(focus: str) -> str:
    low = str(focus or "").lower()
    if "tone" in low:
        return "tone"
    if "articulation" in low or "tongue" in low:
        return "articulation"
    if any(p in low for p in ("timing", "rhythm", "groove", "tempo")):
        return "timing"
    if any(p in low for p in ("harmony", "chord", "voicing")):
        return "harmony"
    if "improv" in low:
        return "improvisation"
    if "phrasing" in low:
        return "phrasing"
    if any(p in low for p in ("sight", "reading")):
        return "sight_reading"
    if "repertoire" in low or "song" in low:
        return "repertoire"
    if "technique" in low:
        return "technique"
    return low or "general"


def _explicit_question_focus(req: CoachRequest) -> tuple[str, bool]:
    low = req.normalized_question.lower()
    if "articulation" in low and any(p in low for p in ("session", "practice", "routine", "work on", "minute")):
        return "articulation", True
    if req.entities.practice_focus_explicit and req.entities.practice_focus:
        return req.entities.practice_focus, True
    if req.constraints.tone_focus or (req.entities.skill_topic == "tone"):
        return "tone", "tone" in low or req.constraints.tone_focus
    for focus, markers in (
        ("timing", ("timing", "metronome", "rhythm session")),
        ("harmony", ("harmony session", "voicing", "chord voicing")),
        ("improvisation", ("improv session", "improvisation session")),
        ("phrasing", ("phrasing session",)),
    ):
        if any(m in low for m in markers):
            return focus, True
    return "", False


def _resolve_plan_focus(req: CoachRequest, history: PracticeHistorySnapshot) -> tuple[str, str]:
    q_focus, q_explicit = _explicit_question_focus(req)
    if q_explicit and q_focus:
        return q_focus, "question_explicit"

    from music_coach_ami.request_resolution import resolve_focus_for_request

    focus, prov = resolve_focus_for_request(
        question_focus=req.entities.practice_focus,
        question_focus_explicit=req.entities.practice_focus_explicit,
        context_focus=req.context.practice_focus,
        skill_topic=req.entities.skill_topic,
    )
    if focus:
        return focus, prov

    if history.unresolved_next_step:
        sec = history.last_section.lower()
        diff = history.recurring_difficulty.lower()
        if "articulation" in diff or "tongue" in diff:
            return "articulation", "history_difficulty"
        if any(p in diff for p in ("timing", "rhythm", "tempo")):
            return "timing", "history_difficulty"
        if any(p in diff for p in ("tone", "air", "register", "breath")):
            return "tone", "history_difficulty"
        if sec:
            return "repertoire", "history_next_step"
    if history.recurring_difficulty:
        diff = history.recurring_difficulty.lower()
        if "articulation" in diff:
            return "articulation", "history_difficulty"
        if any(p in diff for p in ("tone", "register", "breath", "airy")):
            return "tone", "history_difficulty"
        if any(p in diff for p in ("timing", "rhythm")):
            return "timing", "history_difficulty"
    if history.last_focus:
        return history.last_focus, "history_last_focus"
    return "general", "default"


def _resolve_plan_level(req: CoachRequest) -> tuple[str, str]:
    from music_coach_ami.request_resolution import resolve_level_for_request

    return resolve_level_for_request(
        question_level=req.entities.requested_level,
        question_level_explicit=req.entities.requested_level_explicit,
        context_level=req.context.level,
        difficulty_requested="difficult" in req.normalized_question.lower(),
    )


def _level_label(level: str) -> str:
    low = str(level or "").lower()
    if "advanced" in low:
        return "advanced"
    if "intermediate" in low:
        return "intermediate"
    if "begin" in low:
        return "beginner"
    return ""


def _instrument_blocks(
    *,
    family: str,
    focus: str,
    level: str,
    instrument: str,
    history: PracticeHistorySnapshot,
) -> tuple[dict[str, float], dict[str, str]]:
    """Return weight map and block detail text keyed by block label."""
    bucket = _focus_bucket(focus)
    advanced = _level_label(level) == "advanced"
    beginner = _level_label(level) == "beginner"
    upper_register = any(p in history.recurring_difficulty.lower() for p in ("upper register", "high register", "top register"))
    voicing_issue = any(p in history.recurring_difficulty.lower() for p in ("voicing", "voice leading", "chord change"))

    if family == "wind":
        if bucket == "articulation":
            weights = {"warm-up tone centering": 0.15, "single-note tonguing": 0.30, "slur/tongue contrast": 0.25, "musical phrase application": 0.20, "review": 0.10}
            details = {
                "warm-up tone centering": f"Play 4–6 comfortable notes on **{instrument}** with steady air before tonguing.",
                "single-note tonguing": "Tongue repeated notes at a slow tempo; keep tone centered after each attack.",
                "slur/tongue contrast": "Alternate slurred and tongued patterns on one short fragment.",
                "musical phrase application": "Apply the same articulation to a short phrase from your active song or etude.",
            }
        elif bucket == "tone":
            weights = {"long tones": 0.25, "register connection": 0.25, "articulation without tone loss": 0.15, "musical application": 0.25, "review": 0.10}
            details = {
                "long tones": "Hold steady notes in a comfortable register; keep pitch and air even.",
                "register connection": (
                    "Connect low/middle/upper register with slow slurred fragments."
                    if upper_register
                    else "Use slow slurred fragments to keep tone color consistent across registers."
                ),
                "articulation without tone loss": "Compare slurred and tongued attacks on one note without thinning the sound.",
                "musical application": "Transfer the centered tone to a slow phrase from your active song.",
            }
        elif bucket == "timing":
            weights = {"pulse check": 0.20, "subdivision work": 0.30, "section at tempo": 0.30, "review": 0.20}
            details = {
                "pulse check": "Tap or count the beat before playing; confirm where beat 1 lands.",
                "subdivision work": "Practice with a metronome on subdivisions before full tempo.",
                "section at tempo": "Loop the hardest section at a tempo you can stay with cleanly.",
            }
        else:
            weights = {"long tones & tone production": 0.25, "melodic contour & phrasing": 0.30, "rhythm & articulation": 0.25, "full run-through": 0.20}
            details = {
                "long tones & tone production": "Center the sound before pushing range or tempo.",
                "melodic contour & phrasing": "Shape 2–4 bar phrases with clear breath planning.",
                "rhythm & articulation": "Keep attacks clean while maintaining tone.",
                "full run-through": "Play a short section musically, not only mechanically.",
            }
    elif family == "keyboard":
        if bucket == "harmony" or voicing_issue:
            weights = {"warm-up voicings": 0.20, "voice-leading transitions": 0.30, "left-hand pulse": 0.20, "section application": 0.20, "review": 0.10}
            details = {
                "warm-up voicings": "Play simple root-position or shell voicings in the current key.",
                "voice-leading transitions": (
                    "Practice the hardest chord change with minimal hand motion."
                    if voicing_issue
                    else "Move between chords with smooth voice-leading."
                ),
                "left-hand pulse": "Keep a steady pulse while changing harmony.",
                "section application": "Apply the voicings to a verse/chorus loop from your active song.",
            }
        elif bucket == "timing":
            weights = {"time feel": 0.25, "hand coordination": 0.25, "groove pattern": 0.25, "section run-through": 0.25}
            details = {
                "time feel": "Count aloud while playing a simple pattern.",
                "hand coordination": "Separate hands, then combine at a conservative tempo.",
                "groove pattern": "Lock left-hand pulse with a repeating right-hand figure.",
                "section run-through": "Play one section with steady time.",
            }
        else:
            weights = {"technique & hand independence": 0.30, "rhythm & groove": 0.25, "repertoire section": 0.25, "full run-through": 0.20}
            details = {
                "technique & hand independence": "Use a short pattern that challenges both hands separately first.",
                "rhythm & groove": "Keep time steady before adding expression.",
                "repertoire section": "Work one section of your active song with musical shape.",
                "full run-through": "Connect the section into a short performance pass.",
            }
    elif family == "fretted":
        if bucket == "harmony":
            weights = {"chord changes": 0.35, "rhythm / strumming or picking": 0.25, "melody / licks": 0.25, "full run-through": 0.15}
            details = {
                "chord changes": "Loop the hardest change until it is clean 4/5 tries.",
                "rhythm / strumming or picking": "Keep groove steady while changing harmony.",
                "melody / licks": "Add a simple melodic response over the progression.",
                "full run-through": "Play the section musically at a controlled tempo.",
            }
        elif bucket == "timing":
            weights = {"metronome groove": 0.30, "chord rhythm": 0.30, "section loop": 0.25, "review": 0.15}
            details = {
                "metronome groove": "Practice the strum/pick pattern with a metronome.",
                "chord rhythm": "Place chord changes on the correct beats.",
                "section loop": "Loop the section until time stays solid.",
            }
        else:
            weights = {"technique / drills": 0.35, "rhythm / groove": 0.25, "repertoire section": 0.25, "full run-through": 0.15}
            details = {
                "technique / drills": "Isolate the hardest fingering or picking motion.",
                "rhythm / groove": "Keep the pulse steady before speeding up.",
                "repertoire section": "Apply technique work to a real song section.",
                "full run-through": "Play through the section with musical intent.",
            }
    else:
        weights = {"technique / drills": 0.35, "rhythm / groove": 0.25, "repertoire section": 0.25, "full run-through": 0.15}
        details = {
            "technique / drills": "Warm up with focused technical work.",
            "rhythm / groove": "Keep time steady on a simple pattern.",
            "repertoire section": "Apply the work to a section of your active song.",
            "full run-through": "Finish with a musical run-through.",
        }

    if advanced and bucket == "tone":
        details["long tones"] = details.get("long tones", "") + " Use slower tempos and longer holds for precision, not speed."
    if beginner:
        for key in list(details.keys()):
            details[key] = details[key].replace("hardest", "easiest next")

    return weights, details


def _priority_lines(
    *,
    focus: str,
    focus_prov: str,
    instrument: str,
    history: PracticeHistorySnapshot,
    song: str,
    section: str,
) -> tuple[str, str]:
    bucket = _focus_bucket(focus)
    focus_phrase = {
        "tone": f"{instrument} tone",
        "articulation": f"{instrument} articulation",
        "timing": "timing and rhythmic control",
        "harmony": "harmony and voicing work",
        "improvisation": "improvisation vocabulary",
        "phrasing": "phrasing and line shape",
    }.get(bucket, focus or "balanced technique")

    target_song = song or history.last_song
    target_section = section or history.last_section
    if target_section and target_song:
        priority = f"**Today's priority:** {focus_phrase} and the **{target_section}** of **{target_song}**."
    elif target_song:
        priority = f"**Today's priority:** {focus_phrase} on **{target_song}**."
    else:
        priority = f"**Today's priority:** {focus_phrase}."

    why = ""
    if history.available and focus_prov.startswith("history"):
        if history.unresolved_next_step:
            why = f"**Why:** Your recent practice notes said: _{history.unresolved_next_step}_."
        elif history.recurring_difficulty:
            why = f"**Why:** Recent sessions flagged **{history.recurring_difficulty}** as an area that still needs work."
    elif history.available and history.unresolved_next_step and not focus_prov.startswith("question"):
        why = f"**Why:** Your last practice note pointed to: _{history.unresolved_next_step}_."
    return priority, why


def compose_personalized_practice_plan(req: CoachRequest) -> dict[str, Any]:
    from music_coach_ami.request_resolution import display_coach_instrument

    minutes = _minutes(req)
    instrument = display_coach_instrument(req.context.instrument or req.entities.instrument)
    family = instrument_family(instrument)
    level, level_prov = _resolve_plan_level(req)
    history = snapshot_from_coach_context(req.context)
    focus, focus_prov = _resolve_plan_focus(req, history)
    bucket = _focus_bucket(focus)

    song = req.context.active_song_title or history.last_song
    section = req.context.active_section or history.last_section

    q_focus, q_explicit = _explicit_question_focus(req)
    use_tone_plan = bucket == "tone"

    priority, why = _priority_lines(
        focus=focus,
        focus_prov=focus_prov,
        instrument=instrument,
        history=history,
        song=song,
        section=section,
    )

    if use_tone_plan:
        plan = tone_focused_practice_plan(
            instrument,
            minutes,
            level=level,
            song_title=song,
            section=section,
        )
        headline = str(plan.get("headline") or f"**{minutes}-minute {instrument} tone session**")
        direct_parts = [priority]
        if why:
            direct_parts.append(why)
        direct_parts.append(headline)
        direct_parts.append(str(plan.get("goal") or "").strip())
        return {
            "direct_answer": "\n\n".join(p for p in direct_parts if p),
            "practice_steps": list(plan.get("steps") or []),
            "what_to_listen_for": list(plan.get("listen") or []),
            "recommendation": str(plan.get("closing") or "").strip(),
            "progression_criteria": [
                "Advance tempo or range only when the current block stays clean on most repetitions.",
            ],
            "diagnostics": {
                "session_minutes": minutes,
                "resolved_instrument": instrument,
                "instrument_family": family,
                "resolved_level": level,
                "level_provenance": level_prov,
                "resolved_focus": focus,
                "focus_provenance": focus_prov,
                "practice_history_available": history.available,
                "history_signals_used": list(history.signals_used),
                "active_song_title": song or None,
                "active_section": section or None,
                "tone_plan_reused": True,
            },
        }

    chord_focus = any(
        p in req.normalized_question.lower()
        for p in ("chord change", "chord changes", "chord transition", "chord transitions")
    )

    if chord_focus and not use_tone_plan:
        from music_coach_instrument_voice import practice_plan_profile

        weights, focus_line = practice_plan_profile(instrument, chord_focus=True)
        blocks = _allocate(minutes, weights)
        steps = [f"**{m} min** — {label}" for label, m in blocks.items()]
        direct_parts = [priority]
        if why:
            direct_parts.append(why)
        direct_parts.append(f"Here is a **{minutes}-minute** plan for **{instrument}**:")
        return {
            "direct_answer": "\n\n".join(direct_parts),
            "practice_steps": steps,
            "what_to_listen_for": ["Clean harmonic changes before speed", "Steady time through each block"],
            "recommendation": focus_line,
            "progression_criteria": [
                "Advance tempo only when the current block stays clean on most repetitions.",
            ],
            "diagnostics": {
                "session_minutes": minutes,
                "resolved_instrument": instrument,
                "instrument_family": family,
                "resolved_level": level,
                "level_provenance": level_prov,
                "resolved_focus": focus,
                "focus_provenance": focus_prov,
                "practice_history_available": history.available,
                "history_signals_used": list(history.signals_used),
                "chord_focus": True,
                "block_allocation": blocks,
                **blocks,
            },
        }

    weights, details = _instrument_blocks(
        family=family,
        focus=focus,
        level=level,
        instrument=instrument,
        history=history,
    )
    blocks = _allocate(minutes, weights)
    steps = []
    for label, mins in blocks.items():
        detail = details.get(label, "")
        line = f"**{mins} min** — {label}"
        if detail:
            line += f": {detail}"
        steps.append(line)

    listen = []
    if bucket == "articulation":
        listen = ["Clear attacks without a thin or explosive start", "Even tone between slurred and tongued notes"]
    elif bucket == "timing":
        listen = ["Steady pulse on beat 1", "Clean placement of chord or note changes"]
    elif bucket == "harmony":
        listen = ["Smooth voice-leading between chords", "Steady left-hand pulse while harmony changes"]
    elif bucket == "tone":
        listen = ["Centered core tone", "Stable pitch and steady air"]

    direct_parts = [priority]
    if why:
        direct_parts.append(why)
    direct_parts.append(f"Here is a **{minutes}-minute** plan for **{instrument}**:")

    return {
        "direct_answer": "\n\n".join(direct_parts),
        "practice_steps": steps,
        "what_to_listen_for": listen,
        "recommendation": "Log what improved and what still feels unstable in **Practice Log** when you finish.",
        "progression_criteria": [
            "Move to the next block only when the current one stays clean on most repetitions.",
            "Increase tempo or range only after the current tempo feels reliable.",
        ],
        "diagnostics": {
            "session_minutes": minutes,
            "resolved_instrument": instrument,
            "instrument_family": family,
            "resolved_level": level,
            "level_provenance": level_prov,
            "resolved_focus": focus,
            "focus_provenance": focus_prov,
            "practice_history_available": history.available,
            "history_signals_used": list(history.signals_used),
            "history_next_step": history.unresolved_next_step or None,
            "history_recurring_difficulty": history.recurring_difficulty or None,
            "active_song_title": song or None,
            "active_section": section or None,
            "block_allocation": blocks,
            **blocks,
            "explicit_request_overrides_history": q_explicit,
        },
    }
