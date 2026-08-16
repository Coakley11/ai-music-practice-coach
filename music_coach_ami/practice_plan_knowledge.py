"""Personalized practice-plan composition — instrument, level, focus, Practice Log."""

from __future__ import annotations

import re
from typing import Any

from music_coach_ami.practice_history_context import PracticeHistorySnapshot, snapshot_from_coach_context
from music_coach_ami.types import CoachRequest
from music_coach_instrument_voice import instrument_family, tone_focused_practice_plan

METRONOME_APP_NAV_HINT = "**In the app:** Open **Practice tools → Metronome, Tuner & Tone**."


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
    try:
        from practice_focus_coaching import ami_focus_bucket

        bucket = ami_focus_bucket(focus)
        if bucket and bucket != "general":
            return bucket
    except ImportError:
        pass
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
    if "fingerstyle" in low or "finger style" in low:
        return "fingerstyle"
    if "bass line" in low or "bass-line" in low or "walking bass" in low:
        return "bass_line"
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
    if "fingerstyle" in low and any(p in low for p in ("session", "practice", "routine", "work on", "minute", "workout")):
        return "fingerstyle", True
    if re.search(r"\bbass line\b|\bbass-line\b", low) and any(
        p in low for p in ("session", "practice", "routine", "work on", "minute", "workout", "for this song")
    ):
        return "bass line", True
    if req.entities.practice_focus_explicit and req.entities.practice_focus:
        return req.entities.practice_focus, True
    if req.constraints.tone_focus or (req.entities.skill_topic == "tone"):
        return "tone", "tone" in low or req.constraints.tone_focus
    for focus, markers in (
        ("timing", ("timing", "metronome", "rhythm session")),
        ("harmony", ("harmony session", "voicing", "chord voicing")),
        ("improvisation", ("improv session", "improvisation session")),
        ("phrasing", ("phrasing session",)),
        ("fingerstyle", ("fingerstyle session",)),
    ):
        if any(m in low for m in markers):
            return focus, True
    return "", False


def _clean(text: object) -> str:
    return str(text or "").strip()


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
    if focus and prov in {"question", "coach_context"}:
        return focus, prov

    if history.unresolved_next_step:
        step_low = history.unresolved_next_step.lower()
        if any(p in step_low for p in ("phrase", "phrasing", "line shape")):
            return "phrasing", "history_next_step"
        if "bridge" in step_low or _usable_section(history.last_section):
            if history.last_focus:
                return history.last_focus, "history_next_step"
            return "repertoire", "history_next_step"
        diff = history.recurring_difficulty.lower()
        if "articulation" in diff or "tongue" in diff:
            return "articulation", "history_difficulty"
        if any(p in diff for p in ("timing", "rhythm", "tempo")):
            return "timing", "history_difficulty"
        if any(p in diff for p in ("tone", "air", "register", "breath")):
            return "tone", "history_difficulty"
        if "voicing" in diff or "voice leading" in diff:
            return "harmony", "history_difficulty"
        if history.last_focus:
            return history.last_focus, "history_next_step"
    if history.recurring_difficulty:
        diff = history.recurring_difficulty.lower()
        if "articulation" in diff:
            return "articulation", "history_difficulty"
        if any(p in diff for p in ("tone", "register", "breath", "airy")):
            return "tone", "history_difficulty"
        if any(p in diff for p in ("timing", "rhythm")):
            return "timing", "history_difficulty"
        if "voicing" in diff:
            return "harmony", "history_difficulty"
        if "phrasing" in diff or "phrase" in diff:
            return "phrasing", "history_difficulty"
    if history.last_focus:
        return history.last_focus, "history_last_focus"
    if focus:
        return focus, prov
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


def _song_section_phrase(song: str, section: str) -> str:
    song_title = _clean(song)
    sec = _usable_section(section)
    if sec and song_title:
        return f"the **{sec}** of **{song_title}**"
    if song_title:
        return f"**{song_title}**"
    return "your active song"


def _history_thumb_pulse_issue(history: PracticeHistorySnapshot) -> bool:
    diff = history.recurring_difficulty.lower()
    step = history.unresolved_next_step.lower()
    combined = f"{diff} {step}"
    return any(
        p in combined
        for p in ("thumb", "bass pulse", "steady pulse", "loses pulse", "losing pulse", "bass note", "alternating bass")
    )


def _bass_line_blocks(
    *,
    family: str,
    level: str,
    instrument: str,
    song: str,
    section: str,
) -> tuple[dict[str, float], dict[str, str]]:
    """Bass-line focus — instrument family and level shape the work."""
    lvl = _level_label(level) or "intermediate"
    target = _song_section_phrase(song, section)

    if family == "bass":
        if lvl == "beginner":
            weights = {
                "roots on strong beats": 0.30,
                "root–fifth movement": 0.30,
                "short progression loop": 0.25,
                "review": 0.15,
            }
            details = {
                "roots on strong beats": f"Play each chord root on beat 1 on **{instrument}**; keep note length even.",
                "root–fifth movement": "Add the fifth above each root on a simple two-chord loop.",
                "short progression loop": f"Loop a short progression from {target} with roots only.",
                "review": "Replay the loop and note where roots land late or early.",
            }
        elif lvl == "advanced":
            weights = {
                "progression root map": 0.15,
                "approach notes into roots": 0.25,
                "walking / connecting between chords": 0.30,
                "section application": 0.20,
                "review": 0.10,
            }
            details = {
                "progression root map": f"Name each root through {target} before playing.",
                "approach notes into roots": "Use one approach tone into each new root without losing time.",
                "walking / connecting between chords": "Connect chord to chord with a simple walking line that lands on roots.",
                "section application": f"Apply the line to one section of {target}.",
                "review": "Play the section once and note where the line fights the harmony.",
            }
        else:
            weights = {
                "progression root map": 0.15,
                "roots in time": 0.25,
                "chord-tone connection": 0.25,
                "section application": 0.25,
                "review": 0.10,
            }
            details = {
                "progression root map": f"Identify each root in {target} before playing.",
                "roots in time": "Play roots on strong beats with a steady pulse.",
                "chord-tone connection": "Connect roots with chord tones or simple approach notes.",
                "section application": f"Apply the line to one section of {target}.",
                "review": "Play the section once and note where changes feel late.",
            }
    elif family == "keyboard":
        if lvl == "beginner":
            weights = {
                "left-hand roots on strong beats": 0.30,
                "root–fifth left-hand pattern": 0.30,
                "short progression loop": 0.25,
                "review": 0.15,
            }
            details = {
                "left-hand roots on strong beats": "Play left-hand roots on beat 1 only; keep them even.",
                "root–fifth left-hand pattern": "Add a fifth above each root in a simple two-chord loop.",
                "short progression loop": f"Loop a short progression from {target} with left-hand roots only.",
                "review": "Replay and note where the bass hand arrives late.",
            }
        elif lvl == "advanced":
            weights = {
                "walking bass in left hand": 0.30,
                "approach tones & voice leading": 0.25,
                "rhythmic bass patterns": 0.20,
                "section application": 0.15,
                "review": 0.10,
            }
            details = {
                "walking bass in left hand": "Connect chord to chord with a simple walking bass under the harmony.",
                "approach tones & voice leading": "Use smooth bass motion into each new root.",
                "rhythmic bass patterns": "Keep a repeating bass rhythm while harmony changes.",
                "section application": f"Apply the bass movement beneath one section of {target}.",
                "review": "Play once and note where bass and harmony disagree.",
            }
        else:
            weights = {
                "left-hand root movement": 0.25,
                "smooth bass voice leading": 0.30,
                "rhythmic bass patterns": 0.20,
                "section application": 0.25,
            }
            details = {
                "left-hand root movement": "Move left-hand roots on strong beats through the progression.",
                "smooth bass voice leading": "Connect each bass note to the next with minimal jump.",
                "rhythmic bass patterns": "Keep a steady left-hand pulse while chords change.",
                "section application": f"Apply the bass movement beneath one section of {target}.",
            }
    elif family == "fretted":
        if lvl == "beginner":
            weights = {
                "bass-string roots": 0.30,
                "simple alternating bass": 0.30,
                "short progression loop": 0.25,
                "review": 0.15,
            }
            details = {
                "bass-string roots": f"Play each chord root on the bass strings of **{instrument}** on beat 1.",
                "simple alternating bass": "Alternate bass-string roots on two chords slowly.",
                "short progression loop": f"Loop a short progression from {target} with bass-string roots.",
                "review": "Replay and note where the bass pulse breaks.",
            }
        elif lvl == "advanced":
            weights = {
                "independent thumb bass line": 0.25,
                "approach notes on bass strings": 0.25,
                "melody over steady bass": 0.25,
                "section application": 0.15,
                "review": 0.10,
            }
            details = {
                "independent thumb bass line": "Keep a bass line steady while upper voices move independently.",
                "approach notes on bass strings": "Connect roots with simple approach tones on the bass strings.",
                "melody over steady bass": f"Keep melody clear over the bass line in {target}.",
                "section application": f"Apply the bass movement to one section of {target}.",
                "review": "Play once and note where bass and upper voices collide.",
            }
        else:
            weights = {
                "bass-string root movement": 0.25,
                "alternating bass through changes": 0.25,
                "connect roots with chord tones": 0.25,
                "section application": 0.25,
            }
            details = {
                "bass-string root movement": "Play roots on the bass strings on strong beats.",
                "alternating bass through changes": "Keep an alternating bass pattern through two or three chord changes.",
                "connect roots with chord tones": "Move between roots using chord tones or simple approaches.",
                "section application": f"Apply the bass movement to one section of {target}.",
            }
    else:
        weights = {
            "hear / map the roots": 0.25,
            "roots in time": 0.25,
            "simple connecting notes": 0.25,
            "section application": 0.15,
            "review": 0.10,
        }
        details = {
            "hear / map the roots": f"Identify each chord root in {target} before playing.",
            "roots in time": f"Play or sing roots on strong beats on **{instrument}** with steady time.",
            "simple connecting notes": "Connect roots with one simple passing or approach note.",
            "section application": f"Apply the bass-line idea to one section of {target}.",
            "review": "Replay and note where the line loses the harmony.",
        }
    return weights, details


def _plan_uses_metronome(*, steps: list[str], bucket: str) -> bool:
    if bucket == "timing":
        return True
    return "metronome" in " ".join(steps).lower()


def _fingerstyle_blocks(
    *,
    level: str,
    instrument: str,
    song: str,
    section: str,
    history: PracticeHistorySnapshot,
) -> tuple[dict[str, float], dict[str, str]]:
    """Fingerstyle-specific practice blocks — level, song, and log-aware."""
    lvl = _level_label(level) or "intermediate"
    target = _song_section_phrase(song, section)
    thumb_issue = history.available and _history_thumb_pulse_issue(history)

    if thumb_issue:
        weights = {
            "isolated thumb pulse": 0.25,
            "chord transitions with steady bass": 0.30,
            "active-song application": 0.25,
            "melody/bass balance check": 0.10,
            "review": 0.10,
        }
        details = {
            "isolated thumb pulse": "Play a steady bass note or alternating bass on one chord; keep the pulse even before adding fingers.",
            "chord transitions with steady bass": "Move chord to chord without letting the thumb pulse collapse or rush.",
            "active-song application": f"Apply the steady bass pattern to a short loop from {target}.",
            "melody/bass balance check": "Keep melody notes clear while the thumb stays even and unhurried.",
            "review": "Play the loop once without stopping and note where the bass pulse breaks down.",
        }
        return weights, details

    if lvl == "beginner":
        weights = {
            "simple pattern & thumb/finger coordination": 0.30,
            "slow chord-to-chord changes": 0.25,
            "short section loop": 0.25,
            "review": 0.20,
        }
        details = {
            "simple pattern & thumb/finger coordination": (
                f"On **{instrument}**, hold a fixed thumb-on-bass pattern while fingers pluck one upper-string note at a time."
            ),
            "slow chord-to-chord changes": "Move between two or three chords slowly without stopping the picking pattern.",
            "short section loop": f"Loop a very short passage from {target} at a tempo you can keep clean.",
            "review": "Replay the loop and note one fingering or thumb placement fix for next time.",
        }
    elif lvl == "advanced":
        weights = {
            "voice independence": 0.25,
            "melody projection over accompaniment": 0.25,
            "pattern variation & rhythmic displacement": 0.20,
            "musical phrasing with accompaniment": 0.20,
            "review": 0.10,
        }
        details = {
            "voice independence": "Keep bass, inner voices, and melody independent — no collapsing into block chords.",
            "melody projection over accompaniment": f"Project the top-line melody clearly over the pattern in {target}.",
            "pattern variation & rhythmic displacement": "Vary the pattern slightly while keeping time and bass orientation steady.",
            "musical phrasing with accompaniment": "Shape 2–4 bar phrases without losing the underlying accompaniment.",
            "review": "Play one musical pass and note where independence or phrasing breaks down.",
        }
    else:
        weights = {
            "thumb independence": 0.20,
            "picking-pattern consistency": 0.25,
            "active-song application": 0.30,
            "melody/bass balance": 0.15,
            "review": 0.10,
        }
        details = {
            "thumb independence": "Keep a steady bass pulse while fingers play a simple upper-string pattern.",
            "picking-pattern consistency": "Loop one fingerstyle pattern slowly through two or three chord changes.",
            "active-song application": f"Apply that pattern to a short section of {target}.",
            "melody/bass balance": "Keep melody notes clear while the thumb remains even.",
            "review": "Play the section once without stopping and note where the pattern breaks down.",
        }
    return weights, details


def _fretted_phrasing_blocks(*, instrument: str, song: str, section: str) -> tuple[dict[str, float], dict[str, str]]:
    target = _song_section_phrase(song, section)
    weights = {
        "warm-up & tone on single notes": 0.15,
        "2-bar phrase shaping": 0.30,
        "dynamic contour through a section": 0.30,
        "review": 0.25,
    }
    details = {
        "warm-up & tone on single notes": f"Center tone on **{instrument}** with slow single-note or short-phrase attacks.",
        "2-bar phrase shaping": "Work 2-bar fragments slowly; plan where the line rises and settles.",
        "dynamic contour through a section": f"Shape longer lines through {target} with clear peaks and releases.",
        "review": "Replay the hardest 2-bar fragment and note one phrasing fix for next time.",
    }
    return weights, details


def _fretted_improvisation_blocks(*, instrument: str, song: str) -> tuple[dict[str, float], dict[str, str]]:
    target = _song_section_phrase(song, "")
    weights = {
        "guide-tone / chord-tone targets": 0.25,
        "motif development": 0.30,
        "rhythm & articulation in lines": 0.25,
        "review": 0.20,
    }
    details = {
        "guide-tone / chord-tone targets": f"Outline chord tones on **{instrument}** over a short loop from {target}.",
        "motif development": "Develop a 3–5 note motif through sequence, rhythm change, or register shift.",
        "rhythm & articulation in lines": "Keep attacks and note length intentional while improvising.",
        "review": "Record or replay one chorus and note one line you would keep.",
    }
    return weights, details


def _fretted_technique_blocks(*, instrument: str, song: str, section: str, level: str) -> tuple[dict[str, float], dict[str, str]]:
    target = _song_section_phrase(song, section)
    beginner = _level_label(level) == "beginner"
    if beginner:
        weights = {
            "left-hand fingering clarity": 0.30,
            "right-hand picking / strumming control": 0.30,
            "slow section loop": 0.25,
            "review": 0.15,
        }
        details = {
            "left-hand fingering clarity": f"Practice clean fretting on **{instrument}** with minimal finger lift.",
            "right-hand picking / strumming control": "Keep attacks even on a simple repeated pattern.",
            "slow section loop": f"Loop a short passage from {target} slowly and cleanly.",
            "review": "Note one fingering or picking adjustment for next time.",
        }
    else:
        weights = {
            "left-hand efficiency & shifts": 0.25,
            "right-hand accuracy & speed control": 0.30,
            "technique applied to repertoire": 0.30,
            "review": 0.15,
        }
        details = {
            "left-hand efficiency & shifts": "Isolate position shifts or stretches; keep motion economical.",
            "right-hand accuracy & speed control": "Push tempo only where attacks stay clean and even.",
            "technique applied to repertoire": f"Transfer the drill to a demanding passage from {target}.",
            "review": "Replay the passage and note what still breaks down.",
        }
    return weights, details


def _focus_listen_and_progression(bucket: str, *, history: PracticeHistorySnapshot | None = None) -> tuple[list[str], list[str]]:
    listen: list[str] = []
    progression: list[str] = [
        "Move to the next block only when the current one stays clean on most repetitions.",
    ]
    if bucket == "fingerstyle":
        listen = [
            "Steady bass pulse from the thumb",
            "Even note attacks across fingers",
            "Melody audible above accompaniment",
            "No unwanted string noise on changes",
            "Smooth transitions without breaking the picking pattern",
        ]
        progression.append("Add tempo or chord changes only after the pattern stays even on most repetitions.")
    elif bucket == "bass_line":
        listen = [
            "Bass notes line up with chord changes",
            "Steady pulse through the line",
            "Clean movement between roots",
            "The line supports rather than fights the harmony",
        ]
        progression.append("Add connecting notes or tempo only after roots land cleanly on most repetitions.")
    elif bucket == "articulation":
        listen = ["Clear attacks without a thin or explosive start", "Even tone between slurred and tongued notes"]
    elif bucket == "timing":
        listen = ["Steady pulse on beat 1", "Clean placement of chord or note changes"]
        progression.append("Increase tempo only after the current tempo feels reliable.")
    elif bucket == "harmony":
        listen = ["Smooth voice-leading between chords", "Steady left-hand pulse while harmony changes"]
    elif bucket == "tone":
        listen = ["Centered core tone", "Stable pitch and steady air"]
    elif bucket == "phrasing":
        listen = ["Line shape over speed", "Even tone through each 2-bar fragment"]
        progression.append("Extend phrase length only when 2-bar fragments stay shaped and even.")
    elif bucket == "improvisation":
        listen = ["Intentional chord-tone landing", "Rhythmic variety without losing time"]
    elif bucket == "technique":
        listen = ["Clean fretting without buzz", "Even right-hand attacks before speed"]
    if history and history.available and _history_thumb_pulse_issue(history) and bucket == "fingerstyle":
        listen.insert(0, "Thumb pulse stays even through chord changes")
    return listen, progression


def _instrument_blocks(
    *,
    family: str,
    focus: str,
    level: str,
    instrument: str,
    history: PracticeHistorySnapshot,
    song: str = "",
    section: str = "",
) -> tuple[dict[str, float], dict[str, str]]:
    """Return weight map and block detail text keyed by block label."""
    bucket = _focus_bucket(focus)
    advanced = _level_label(level) == "advanced"
    beginner = _level_label(level) == "beginner"
    upper_register = any(p in history.recurring_difficulty.lower() for p in ("upper register", "high register", "top register"))
    voicing_issue = any(p in history.recurring_difficulty.lower() for p in ("voicing", "voice leading", "chord change"))

    if bucket == "bass_line":
        return _bass_line_blocks(
            family=family,
            level=level,
            instrument=instrument,
            song=song,
            section=section,
        )

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
        if bucket == "fingerstyle":
            return _fingerstyle_blocks(
                level=level,
                instrument=instrument,
                song=song,
                section=section,
                history=history,
            )
        if bucket == "phrasing":
            return _fretted_phrasing_blocks(instrument=instrument, song=song, section=section)
        if bucket == "improvisation":
            return _fretted_improvisation_blocks(instrument=instrument, song=song)
        if bucket == "technique":
            return _fretted_technique_blocks(
                instrument=instrument,
                song=song,
                section=section,
                level=level,
            )
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
    elif family == "bass":
        weights = {
            "groove & note length": 0.30,
            "root movement & chord tones": 0.30,
            "lock with pulse / harmony": 0.25,
            "section application": 0.15,
        }
        target = _song_section_phrase(song, section)
        details = {
            "groove & note length": f"Keep note length even on **{instrument}** before adding faster lines.",
            "root movement & chord tones": "Outline roots and chord tones through the progression.",
            "lock with pulse / harmony": "Keep the line aligned with the harmony and a steady pulse.",
            "section application": f"Apply the line to one section of {target}.",
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


def _usable_section(section: str) -> str:
    text = _clean(section)
    if not text:
        return ""
    low = text.lower()
    if low in {"full song", "full", "all", "song", "entire song"}:
        return ""
    return text


def _focus_display_phrase(bucket: str, instrument: str, focus: str) -> str:
    phrases = {
        "tone": f"{instrument} tone",
        "articulation": f"{instrument} articulation",
        "timing": "timing and rhythmic control",
        "rhythm_groove": "strumming, groove, and rhythmic patterns" if "strum" in str(focus or "").lower() else "rhythm and groove",
        "harmony": "harmony and voicing",
        "improvisation": "improvisation vocabulary",
        "phrasing": "phrasing and line shape",
        "fingerstyle": "fingerstyle technique",
        "bass_line": "bass-line development",
        "technique": f"{instrument} technique",
        "melody": "melody and motif development",
        "repertoire": "repertoire work",
    }
    if bucket in phrases:
        return phrases[bucket]
    cleaned = _clean(focus)
    return cleaned or "balanced technique"


def _format_priority_line(*, focus_phrase: str, song: str = "", section: str = "") -> str:
    sec = _usable_section(section)
    song_title = _clean(song)
    if sec and song_title:
        return f"**Today's priority:** {focus_phrase} in the **{sec}** of **{song_title}**."
    if song_title:
        if focus_phrase.endswith("work"):
            return f"**Today's priority:** {focus_phrase} on **{song_title}**."
        if focus_phrase in {
            "harmony and voicing",
            "phrasing and line shape",
            "fingerstyle technique",
            "bass-line development",
            "strumming, groove, and rhythmic patterns",
            "rhythm and groove",
            "timing and rhythmic control",
            "melody and motif development",
        }:
            preposition = "across" if focus_phrase == "harmony and voicing" else "in"
            return f"**Today's priority:** {focus_phrase} {preposition} **{song_title}**."
        return f"**Today's priority:** {focus_phrase} in **{song_title}**."
    return f"**Today's priority:** {focus_phrase}."


def _history_why_line(history: PracticeHistorySnapshot, *, focus_prov: str) -> str:
    if not history.available or not focus_prov.startswith("history"):
        return ""
    if history.unresolved_next_step:
        step = history.unresolved_next_step
        sec = _usable_section(history.last_section)
        if sec and sec.lower() in step.lower():
            return f"**Why:** Your recent practice note says the **{sec}** still needs slow, focused work."
        if "phrase" in step.lower() or "phrasing" in step.lower():
            return "**Why:** Your last practice note says phrasing there still needs slow, shaped work."
        return f"**Why:** Your last practice note says: _{step}_."
    if history.recurring_difficulty:
        diff = history.recurring_difficulty
        if "upper register" in diff.lower() or "register" in diff.lower():
            return "**Why:** Upper-register tone has come up repeatedly in your recent sessions."
        if "voicing" in diff.lower():
            return "**Why:** Voicing transitions have been a recurring challenge in recent sessions."
        return f"**Why:** **{diff}** has come up repeatedly in your recent sessions."
    if history.last_focus and focus_prov == "history_last_focus":
        return f"**Why:** **{history.last_focus}** has been your most recent practice focus."
    return ""


def _resolve_plan_song_section(
    req: CoachRequest,
    history: PracticeHistorySnapshot,
    focus_prov: str,
) -> tuple[str, str]:
    active_song = _clean(req.context.active_song_title)
    active_section = _usable_section(req.context.active_section)
    if focus_prov.startswith("history"):
        song = _clean(history.last_song) or active_song
        section = _usable_section(history.last_section) or active_section
        if history.unresolved_next_step and _usable_section(history.last_section):
            section = _usable_section(history.last_section)
        return song, section
    song = active_song or _clean(history.last_song)
    section = active_section or _usable_section(history.last_section)
    return song, section


def _history_drives_continuity(history: PracticeHistorySnapshot, focus_prov: str) -> bool:
    if not history.available or not focus_prov.startswith("history"):
        return False
    return bool(history.unresolved_next_step or history.recurring_difficulty or history.last_focus)


def _history_continuity_blocks(
    *,
    family: str,
    instrument: str,
    song: str,
    section: str,
    focus_bucket: str,
    history: PracticeHistorySnapshot,
) -> tuple[dict[str, float], dict[str, str]] | None:
    sec = _usable_section(section)
    song_title = _clean(song)
    if focus_bucket == "phrasing" and sec:
        sec_label = sec
        weights = {
            "warm-up / tone centering": 0.15,
            "slow 2-bar phrase shaping": 0.25,
            f"{sec_label.lower()} at controlled tempo": 0.35,
            "section-to-song application": 0.15,
            "review": 0.10,
        }
        details = {
            "warm-up / tone centering": f"Center tone and air on **{instrument}** before shaping lines.",
            "slow 2-bar phrase shaping": "Work 2-bar fragments slowly; shape the line before adding tempo.",
            f"{sec_label.lower()} at controlled tempo": (
                f"Loop the **{sec_label}** of **{song_title}** at a tempo you can phrase cleanly."
                if song_title
                else f"Loop the **{sec_label}** at a tempo you can phrase cleanly."
            ),
            "section-to-song application": (
                f"Connect the **{sec_label}** back into a longer pass of **{song_title}**."
                if song_title
                else f"Connect the **{sec_label}** into a longer musical pass."
            ),
            "review": "Replay the hardest 2-bar fragment and note one phrasing fix for next time.",
        }
        return weights, details
    if focus_bucket == "tone" and any(p in history.recurring_difficulty.lower() for p in ("register", "upper", "breath", "airy")):
        weights = {
            "long tones": 0.25,
            "register connection": 0.30,
            "tone through attacks": 0.15,
            "musical application": 0.20,
            "review": 0.10,
        }
        details = {
            "long tones": "Hold steady notes in a comfortable register before stretching upward.",
            "register connection": "Use slow slurred fragments to connect into the upper register without thinning.",
            "tone through attacks": "Keep the same centered tone when tonguing or starting notes.",
            "musical application": (
                f"Apply the tone work to a slow phrase from **{song_title}**."
                if song_title
                else "Apply the tone work to a slow phrase from your active song."
            ),
            "review": "Replay the register that still feels unstable.",
        }
        return weights, details
    if focus_bucket == "harmony" and "voicing" in history.recurring_difficulty.lower():
        weights = {
            "warm-up voicings": 0.15,
            "voice-leading transitions": 0.35,
            "left-hand pulse": 0.20,
            "section application": 0.20,
            "review": 0.10,
        }
        details = {
            "warm-up voicings": "Review shell or root-position voicings in the current key.",
            "voice-leading transitions": "Isolate the voicing change that still feels awkward; move smoothly between chords.",
            "left-hand pulse": "Keep a steady pulse while the harmony changes.",
            "section application": (
                f"Apply the voicings to a loop from **{song_title}**."
                if song_title
                else "Apply the voicings to a loop from your active song."
            ),
            "review": "Replay the hardest transition once more at a calm tempo.",
        }
        return weights, details
    if sec and song_title and focus_bucket in {"repertoire", "general"}:
        weights = {
            "warm-up": 0.15,
            f"slow work on {sec.lower()}": 0.35,
            "controlled run-through": 0.30,
            "review": 0.20,
        }
        details = {
            "warm-up": f"Warm up comfortably on **{instrument}** before section work.",
            f"slow work on {sec.lower()}": f"Practice the **{sec}** of **{song_title}** slowly and steadily.",
            "controlled run-through": f"Connect the **{sec}** into a longer pass of **{song_title}**.",
            "review": f"Replay the **{sec}** and note what still needs attention.",
        }
        return weights, details
    return None


def _priority_lines(
    *,
    focus: str,
    focus_prov: str,
    instrument: str,
    history: PracticeHistorySnapshot,
    song: str,
    section: str,
) -> tuple[str, str, list[str]]:
    bucket = _focus_bucket(focus)
    focus_phrase = _focus_display_phrase(bucket, instrument, focus)
    priority = _format_priority_line(
        focus_phrase=focus_phrase,
        song=song,
        section=section,
    )
    why = _history_why_line(history, focus_prov=focus_prov)
    signals_used: list[str] = []
    if why:
        if history.unresolved_next_step and focus_prov.startswith("history"):
            signals_used.append("unresolved_next_step")
        elif history.recurring_difficulty and "history_difficulty" in focus_prov:
            signals_used.append("recurring_difficulty")
        elif history.last_focus and focus_prov == "history_last_focus":
            signals_used.append("last_focus")
    return priority, why, signals_used


def _append_practice_app_hints(direct_parts: list[str], *, steps: list[str], bucket: str) -> None:
    if _plan_uses_metronome(steps=steps, bucket=bucket):
        direct_parts.append(METRONOME_APP_NAV_HINT)


def compose_personalized_practice_plan(req: CoachRequest) -> dict[str, Any]:
    from music_coach_ami.request_resolution import display_coach_instrument

    minutes = _minutes(req)
    instrument = display_coach_instrument(req.entities.instrument or req.context.instrument)
    family = instrument_family(instrument)
    level, level_prov = _resolve_plan_level(req)
    history = snapshot_from_coach_context(req.context)
    focus, focus_prov = _resolve_plan_focus(req, history)
    bucket = _focus_bucket(focus)

    song, section = _resolve_plan_song_section(req, history, focus_prov)

    q_focus, q_explicit = _explicit_question_focus(req)
    use_tone_plan = bucket == "tone" and not _history_drives_continuity(history, focus_prov)

    priority, why, history_signals_used = _priority_lines(
        focus=focus,
        focus_prov=focus_prov,
        instrument=instrument,
        history=history,
        song=song,
        section=section,
    )

    continuity = _history_continuity_blocks(
        family=family,
        instrument=instrument,
        song=song,
        section=section,
        focus_bucket=bucket,
        history=history,
    ) if _history_drives_continuity(history, focus_prov) else None

    base_diag = {
        "session_minutes": minutes,
        "resolved_instrument": instrument,
        "instrument_family": family,
        "resolved_level": level,
        "level_provenance": level_prov,
        "resolved_focus": focus,
        "focus_provenance": focus_prov,
        "practice_history_available": history.available,
        "history_signals_present": list(history.signals_used),
        "history_signals_used_in_plan": history_signals_used,
        "history_influenced_plan": bool(history_signals_used or continuity),
        "history_next_step": history.unresolved_next_step or None,
        "history_recurring_difficulty": history.recurring_difficulty or None,
        "active_song_title": song or None,
        "active_section": section or None,
        "explicit_request_overrides_history": q_explicit,
    }

    if continuity:
        weights, details = continuity
        blocks = _allocate(minutes, weights)
        steps = []
        for label, mins in blocks.items():
            detail = details.get(label, "")
            line = f"**{mins} min** — {label}"
            if detail:
                line += f": {detail}"
            steps.append(line)
        direct_parts = [priority]
        if why:
            direct_parts.append(why)
        direct_parts.append(f"Here is a **{minutes}-minute** plan for **{instrument}**:")
        _append_practice_app_hints(direct_parts, steps=steps, bucket=bucket)
        listen = ["Musical shape over speed", "Clean phrasing at a controlled tempo"]
        if bucket == "phrasing":
            listen = ["Line shape over speed", "Even tone through each 2-bar fragment"]
        elif bucket == "tone":
            listen = ["Centered core tone", "Stable pitch through register changes"]
        elif bucket == "harmony":
            listen = ["Smooth voicing motion", "Steady pulse while harmony changes"]
        return {
            "direct_answer": "\n\n".join(direct_parts),
            "practice_steps": steps,
            "what_to_listen_for": listen,
            "recommendation": "Log what improved and what still feels unstable in **Practice Log** when you finish.",
            "progression_criteria": [
                "Move to the next block only when the current one stays clean on most repetitions.",
            ],
            "diagnostics": {**base_diag, "block_allocation": blocks, **blocks, "history_continuity_blocks": True},
        }

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
        tone_steps = list(plan.get("steps") or [])
        _append_practice_app_hints(direct_parts, steps=tone_steps, bucket=bucket)
        return {
            "direct_answer": "\n\n".join(p for p in direct_parts if p),
            "practice_steps": tone_steps,
            "what_to_listen_for": list(plan.get("listen") or []),
            "recommendation": str(plan.get("closing") or "").strip(),
            "progression_criteria": [
                "Advance tempo or range only when the current block stays clean on most repetitions.",
            ],
            "diagnostics": {
                **base_diag,
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
                **base_diag,
                "chord_focus": True,
                "block_allocation": blocks,
                **blocks,
            },
        }

    try:
        from practice_focus_coaching import (
            listen_and_progression_for_focus,
            should_prefer_policy_plan,
            timed_practice_blocks,
        )
    except ImportError:
        should_prefer_policy_plan = lambda _f: False  # type: ignore[assignment,misc]
        timed_practice_blocks = None  # type: ignore[assignment]
        listen_and_progression_for_focus = None  # type: ignore[assignment]

    if (
        timed_practice_blocks
        and should_prefer_policy_plan(focus)
        and not use_tone_plan
    ):
        weights, details = timed_practice_blocks(
            instrument,
            focus,
            song=song,
            section=section,
            level=level,
        )
        blocks = _allocate(minutes, weights)
        steps = []
        for label, mins in blocks.items():
            detail = details.get(label, "")
            line = f"**{mins} min** — {label}"
            if detail:
                line += f": {detail}"
            steps.append(line)
        listen, progression = listen_and_progression_for_focus(instrument, focus)
        direct_parts = [priority]
        if why:
            direct_parts.append(why)
        direct_parts.append(f"Here is a **{minutes}-minute** plan for **{instrument}**:")
        _append_practice_app_hints(direct_parts, steps=steps, bucket=bucket)
        extra = {}
        try:
            from practice_focus_coaching import context_prompt_block

            extra["practice_focus_prompt"] = context_prompt_block(instrument, focus, role="ami")
        except ImportError:
            pass
        return {
            "direct_answer": "\n\n".join(direct_parts),
            "practice_steps": steps,
            "what_to_listen_for": listen,
            "recommendation": "Log what improved and what still feels unstable in **Practice Log** when you finish.",
            "progression_criteria": progression,
            "diagnostics": {
                **base_diag,
                "focus_profile": bucket,
                "policy_plan": True,
                "block_allocation": blocks,
                **blocks,
                **extra,
            },
        }

    weights, details = _instrument_blocks(
        family=family,
        focus=focus,
        level=level,
        instrument=instrument,
        history=history,
        song=song,
        section=section,
    )
    blocks = _allocate(minutes, weights)
    steps = []
    for label, mins in blocks.items():
        detail = details.get(label, "")
        line = f"**{mins} min** — {label}"
        if detail:
            line += f": {detail}"
        steps.append(line)

    listen, progression = _focus_listen_and_progression(bucket, history=history)

    direct_parts = [priority]
    if why:
        direct_parts.append(why)
    direct_parts.append(f"Here is a **{minutes}-minute** plan for **{instrument}**:")
    _append_practice_app_hints(direct_parts, steps=steps, bucket=bucket)

    return {
        "direct_answer": "\n\n".join(direct_parts),
        "practice_steps": steps,
        "what_to_listen_for": listen,
        "recommendation": "Log what improved and what still feels unstable in **Practice Log** when you finish.",
        "progression_criteria": progression,
        "diagnostics": {
            **base_diag,
            "focus_profile": bucket,
            "history_specialized_blocks": bool(
                history.available and bucket == "fingerstyle" and _history_thumb_pulse_issue(history)
            ),
            "block_allocation": blocks,
            **blocks,
        },
    }
