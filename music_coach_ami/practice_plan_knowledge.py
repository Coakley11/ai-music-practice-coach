"""Personalized practice-plan composition — instrument, level, focus, Practice Log."""

from __future__ import annotations

import re
from typing import Any

from dataclasses import dataclass, field

from music_coach_ami.practice_history_context import PracticeHistorySnapshot, snapshot_from_coach_context
from music_coach_ami.types import CoachRequest
from music_coach_instrument_voice import instrument_family, tone_focused_practice_plan

METRONOME_APP_NAV_HINT = "**In the app:** Open **Practice tools → Metronome, Tuner & Tone**."


@dataclass
class _ChordToneText:
    """Pre-computed text snippets for chord-tone exercises."""
    gt_list: str = ""
    first_vl: str = ""
    vl_chain: str = ""
    root_list: str = ""
    first_pair_chord_names: str = ""


def _chord_tone_exercise_text(chords: list[str]) -> _ChordToneText:
    """Build concrete note-name exercise text from a list of chord symbols."""
    if not chords:
        return _ChordToneText()
    try:
        from music_theory import guide_tones_for_chord, guide_tone_voice_leading, friendly_note_name

        unique_chords: list[str] = []
        seen: set[str] = set()
        for c in chords:
            for part in str(c).split("|"):
                cleaned = part.strip()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    unique_chords.append(cleaned)
        if not unique_chords:
            return _ChordToneText()

        gt_parts: list[str] = []
        for ch in unique_chords[:6]:
            root, third, seventh = guide_tones_for_chord(ch)
            if seventh:
                gt_parts.append(f"{ch}: {third} (3rd) and {seventh} (7th)")
            elif third:
                gt_parts.append(f"{ch}: {third} (3rd)")
        gt_list = "Here are the guide tones: " + "; ".join(gt_parts) + "." if gt_parts else ""

        vl = guide_tone_voice_leading(unique_chords[:8])
        vl_steps = [e["voice_lead"] for e in vl if e["voice_lead"]]
        first_vl = vl_steps[0] if vl_steps else ""
        vl_chain = ", ".join(vl_steps[:6]) if vl_steps else ""

        roots = [friendly_note_name(guide_tones_for_chord(ch)[0]) for ch in unique_chords[:6]]
        root_list = ", ".join(roots) if roots else ""

        pair_names = ", ".join(unique_chords[:2]) if len(unique_chords) >= 2 else unique_chords[0] if unique_chords else ""

        return _ChordToneText(
            gt_list=gt_list,
            first_vl=first_vl,
            vl_chain=vl_chain,
            root_list=root_list,
            first_pair_chord_names=pair_names,
        )
    except Exception:
        return _ChordToneText()


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
    if "tone" in low and "guide" not in low:
        return "tone"
    if "articulation" in low or "tongue" in low:
        return "articulation"
    if any(p in low for p in ("timing", "rhythm", "groove", "tempo", "syncopat")):
        return "timing"
    if "guide tone" in low or "guide-tone" in low:
        return "guide_tones"
    if any(p in low for p in ("pentatonic", "scale")):
        return "pentatonics"
    if "bebop" in low:
        return "bebop_phrasing"
    if any(p in low for p in ("strum", "barre", "double stop", "triad")):
        return "guitar_rhythm"
    if any(p in low for p in ("harmony", "chord", "voicing", "voice leading",
                               "inversion", "reharmoni", "comping")):
        return "harmony"
    if any(p in low for p in ("improv", "solo", "lead guitar")):
        return "improvisation"
    if "phrasing" in low:
        return "phrasing"
    if "fingerstyle" in low or "finger style" in low:
        return "fingerstyle"
    if "bass line" in low or "bass-line" in low or "walking bass" in low:
        return "bass_line"
    if "dynamic" in low:
        return "dynamics"
    if any(p in low for p in ("breath", "endurance", "range")):
        return "breath_endurance"
    if any(p in low for p in ("ear train", "pitch accura")):
        return "ear_training"
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


def _pentatonic_blocks(
    *,
    family: str,
    level: str,
    instrument: str,
    song: str,
    section: str,
    chords: list[str] | None = None,
) -> tuple[dict[str, float], dict[str, str]]:
    lvl = _level_label(level) or "intermediate"
    target = _song_section_phrase(song, section)
    gt = _chord_tone_exercise_text(chords or [])

    if lvl == "beginner":
        weights = {
            "learn the pentatonic shape": 0.30,
            "pentatonic on chord roots": 0.25,
            "short pentatonic phrases": 0.25,
            "review": 0.20,
        }
        if family == "keyboard":
            details = {
                "learn the pentatonic shape": f"Play the major pentatonic scale in the song key with your right hand, one octave up and down on **{instrument}**.",
                "pentatonic on chord roots": f"Over each chord in {target}, play the root, then walk up three pentatonic notes and back.",
                "short pentatonic phrases": "Create a simple 3–4 note phrase using only pentatonic notes; repeat it over two chord changes.",
                "review": "Play your best short phrase twice and check that it lands on a chord tone on beat 1.",
            }
        elif family == "fretted":
            details = {
                "learn the pentatonic shape": f"Practice the first pentatonic box shape on **{instrument}** in the song key, ascending and descending slowly.",
                "pentatonic on chord roots": f"Over each chord in {target}, start on the root and play four pentatonic notes up.",
                "short pentatonic phrases": "Use three or four pentatonic notes to make a short melodic idea; play it over two different chords.",
                "review": "Play the passage slowly and check that your phrase resolves to a chord tone.",
            }
        elif family == "wind":
            root_hint = f" The chord roots are: {gt.root_list}." if gt.root_list else ""
            details = {
                "learn the pentatonic shape": f"Play the minor pentatonic scale in the song key on **{instrument}**, one octave up and down, with even tone and steady air.",
                "pentatonic on chord roots": f"Over each chord in {target}, start on the root and play three pentatonic notes up, then back down.{root_hint}",
                "short pentatonic phrases": f"Create a simple 3-note pentatonic phrase and repeat it over {gt.first_pair_chord_names or 'two chords'}. Breathe at the end of each phrase.",
                "review": "Play your best phrase with a metronome. Does the tone stay centered? Does the phrase land on a chord tone on beat 1?",
            }
        else:
            details = {
                "learn the pentatonic shape": f"Play the pentatonic scale in the song key on **{instrument}**, one octave up and down evenly.",
                "pentatonic on chord roots": f"Over each chord in {target}, start on the root and walk up three pentatonic notes.",
                "short pentatonic phrases": "Make a simple 3–4 note phrase with pentatonic notes; repeat it over two chords.",
                "review": "Play your phrase and confirm it resolves to a chord tone on beat 1.",
            }
    elif lvl == "advanced":
        weights = {
            "pentatonic superimposition": 0.25,
            "pentatonic sequences & patterns": 0.25,
            "pentatonic across chord changes": 0.25,
            "creative application": 0.15,
            "review": 0.10,
        }
        if family == "keyboard":
            details = {
                "pentatonic superimposition": f"Over a ii–V–I in {target}, try different pentatonic scales: e.g. major pentatonic from the 5th of the I chord, minor pentatonic from the root of the ii.",
                "pentatonic sequences & patterns": "Play intervallic pentatonic patterns (3rds, 4ths) across the full range; vary rhythm.",
                "pentatonic across chord changes": f"Improvise through a section of {target} using only pentatonic choices that match each chord.",
                "creative application": "Combine pentatonic runs with chromatic approach notes for melodic variety.",
                "review": "Record one chorus and identify where pentatonic choices clashed with the harmony.",
            }
        elif family == "fretted":
            details = {
                "pentatonic superimposition": f"Over chord changes in {target}, shift pentatonic shapes: e.g. play the pentatonic built from the 3rd or 5th of each chord.",
                "pentatonic sequences & patterns": "Run pentatonic patterns in 4ths or string-skipping sequences across multiple positions.",
                "pentatonic across chord changes": f"Improvise through {target} choosing the best pentatonic for each chord.",
                "creative application": "Mix pentatonic runs with bends, slides, and chromatic approach notes.",
                "review": "Record one pass and note where note choices fought the harmony.",
            }
        elif family == "wind":
            details = {
                "pentatonic superimposition": f"Over the harmony in {target}, experiment with different pentatonic scale choices for each chord — not just the obvious major/minor pentatonic.",
                "pentatonic sequences & patterns": "Practice pentatonic sequences in 3rds and 4ths across the full range with even articulation.",
                "pentatonic across chord changes": f"Improvise through {target} choosing pentatonic material that outlines each chord's quality.",
                "creative application": "Add enclosures and chromatic approaches to pentatonic lines for bebop flavor.",
                "review": "Play one full pass and note where the pentatonic choice felt weak over the harmony.",
            }
        else:
            details = {
                "pentatonic superimposition": f"Over the harmony in {target}, try pentatonic scales built on different chord tones for color.",
                "pentatonic sequences & patterns": "Practice intervallic pentatonic sequences across the range of your instrument.",
                "pentatonic across chord changes": f"Improvise through {target} with pentatonic material matched to each chord.",
                "creative application": "Add rhythmic displacement or chromatic approach tones to pentatonic lines.",
                "review": "Record one pass and identify where note choices need adjustment.",
            }
    else:
        weights = {
            "pentatonic scale warmup": 0.20,
            "pentatonic over chord tones": 0.25,
            "pentatonic melodic phrases": 0.25,
            "song application": 0.20,
            "review": 0.10,
        }
        if family == "keyboard":
            details = {
                "pentatonic scale warmup": f"Play the major pentatonic in the song key with both hands on **{instrument}**, two octaves.",
                "pentatonic over chord tones": f"Over each chord in {target}, improvise short lines using the pentatonic scale, landing on the 3rd or root at each chord change.",
                "pentatonic melodic phrases": "Build a 2-bar melodic idea using pentatonic notes; vary the rhythm and repeat over a different chord.",
                "song application": f"Improvise through a section of {target} using pentatonic material.",
                "review": "Replay the section and note where your pentatonic lines clashed with the chord.",
            }
        elif family == "fretted":
            details = {
                "pentatonic scale warmup": f"Play the pentatonic scale in two positions on **{instrument}**, connecting them with a slide or shift.",
                "pentatonic over chord tones": f"Over each chord in {target}, play a pentatonic phrase that starts or lands on a chord tone.",
                "pentatonic melodic phrases": "Create a 4-note pentatonic lick and move it through three different chords, adapting as needed.",
                "song application": f"Improvise through a section of {target} using your best pentatonic phrases.",
                "review": "Replay and note which chord changes needed a different pentatonic approach.",
            }
        elif family == "wind":
            root_hint = f" Chord roots: {gt.root_list}." if gt.root_list else ""
            details = {
                "pentatonic scale warmup": f"Play the pentatonic scale on **{instrument}** through two octaves with even tone and steady air.",
                "pentatonic over chord tones": f"Over each chord in {target}, play a pentatonic phrase that resolves to the 3rd or root on beat 1.{root_hint}",
                "pentatonic melodic phrases": f"Build a 2-bar pentatonic phrase over {gt.first_pair_chord_names or 'two chords'}, then vary the rhythm or direction. Breathe at phrase ends.",
                "song application": f"Improvise through {target} using pentatonic lines. Land on chord tones at each change and breathe at natural phrase breaks.",
                "review": "Replay and note where pentatonic choices clashed with the harmony. Did your phrases resolve on chord tones?",
            }
        else:
            root_hint = f" Chord roots: {gt.root_list}." if gt.root_list else ""
            details = {
                "pentatonic scale warmup": f"Play the pentatonic scale on **{instrument}** through two octaves evenly.",
                "pentatonic over chord tones": f"Over each chord in {target}, play pentatonic phrases that land on chord tones.{root_hint}",
                "pentatonic melodic phrases": f"Build a 2-bar pentatonic phrase over {gt.first_pair_chord_names or 'two chords'} and vary rhythm or direction.",
                "song application": f"Improvise through {target} with pentatonic material, targeting chord tones on strong beats.",
                "review": "Replay and note where note choices need adjustment.",
            }
    return weights, details


def _guide_tone_blocks(
    *,
    family: str,
    level: str,
    instrument: str,
    song: str,
    section: str,
    chords: list[str] | None = None,
) -> tuple[dict[str, float], dict[str, str]]:
    lvl = _level_label(level) or "intermediate"
    target = _song_section_phrase(song, section)
    gt = _chord_tone_exercise_text(chords or [])

    if lvl == "beginner":
        weights = {
            "find the 3rds and 7ths": 0.30,
            "connect guide tones between two chords": 0.30,
            "guide-tone line through a short progression": 0.25,
            "review": 0.15,
        }
        find_text = f"For each chord in {target}, play the 3rd and then the 7th as whole notes on **{instrument}**."
        if gt.gt_list:
            find_text += f" {gt.gt_list} Play each note, hold it, and listen to how it sounds against the chord."
        connect_text = "Play the 7th of one chord, then move by step to the 3rd of the next chord. Hold each note for two beats."
        if gt.first_vl:
            connect_text += f" Start with: {gt.first_vl}."
        if family == "wind":
            details = {
                "find the 3rds and 7ths": find_text,
                "connect guide tones between two chords": connect_text + " Keep the air steady through each note.",
                "guide-tone line through a short progression": f"String guide tones together through {target} — you should hear a simple melody made of 3rds and 7ths.",
                "review": "Play the guide-tone line without accompaniment and check that it sounds like music, not random notes. Can you sing it back?",
            }
        elif family == "keyboard":
            details = {
                "find the 3rds and 7ths": find_text.replace("as whole notes on", "in your right hand on") + " Play the root in your left hand.",
                "connect guide tones between two chords": connect_text.replace("Play the", "In your right hand, play the"),
                "guide-tone line through a short progression": f"Play a guide-tone melody through {target} in your right hand over left-hand roots. It should sound like a simple song.",
                "review": "Play the guide-tone line alone — does it move smoothly? Can you hear it as a melody?",
            }
        else:
            details = {
                "find the 3rds and 7ths": find_text,
                "connect guide tones between two chords": connect_text,
                "guide-tone line through a short progression": f"Play guide tones through {target} as a simple melody.",
                "review": "Play the line alone and check it moves smoothly between chords.",
            }
    elif lvl == "advanced":
        weights = {
            "guide-tone voice leading across the form": 0.25,
            "embellished guide-tone lines": 0.25,
            "guide tones as improvisation framework": 0.25,
            "creative application": 0.15,
            "review": 0.10,
        }
        form_text = f"Map a continuous guide-tone line (3rds and 7ths) through the full form of {target} with minimal voice-leading motion."
        if gt.gt_list:
            form_text += f" {gt.gt_list}"
        if gt.vl_chain:
            form_text += f" Voice-leading path: {gt.vl_chain}."
        details = {
            "guide-tone voice leading across the form": form_text,
            "embellished guide-tone lines": "Add passing tones, neighbor tones, and enclosures around each guide tone while keeping the line's shape. Target: embellished line still resolves to the correct guide tone on each downbeat.",
            "guide tones as improvisation framework": f"Improvise through {target} using guide tones as target notes on strong beats, filling between with scales or chromatic movement.",
            "creative application": "Vary rhythm and articulation on the guide-tone line. Try displacing targets by an eighth note; try starting lines from the 7th instead of the 3rd.",
            "review": "Record one pass and check: do guide tones still anchor the line on strong beats despite embellishment?",
        }
    else:
        weights = {
            "identify guide tones for each chord": 0.20,
            "smooth guide-tone connections": 0.30,
            "guide-tone line through a section": 0.25,
            "song application": 0.15,
            "review": 0.10,
        }
        id_text = f"Play the 3rd and 7th of each chord in {target}."
        if gt.gt_list:
            id_text += f" {gt.gt_list}"
        connect_text = "Connect the 7th of one chord to the 3rd of the next by the smoothest path. Use half notes."
        if gt.vl_chain:
            connect_text += f" Voice-leading path: {gt.vl_chain}."
        details = {
            "identify guide tones for each chord": id_text,
            "smooth guide-tone connections": connect_text,
            "guide-tone line through a section": f"Play a continuous guide-tone line through {target} — it should sound like a melody, not isolated intervals.",
            "song application": f"Add simple passing tones between guide tones while playing through {target}. Stay on guide tones on beats 1 and 3.",
            "review": "Play the guide-tone line without accompaniment. Is the voice leading stepwise? Does it sing?",
        }
    return weights, details


def _bebop_phrasing_blocks(
    *,
    family: str,
    level: str,
    instrument: str,
    song: str,
    section: str,
    chords: list[str] | None = None,
) -> tuple[dict[str, float], dict[str, str]]:
    lvl = _level_label(level) or "intermediate"
    target = _song_section_phrase(song, section)
    gt = _chord_tone_exercise_text(chords or [])

    if lvl == "beginner":
        weights = {
            "swing eighth-note feel": 0.30,
            "simple bebop scale fragment": 0.30,
            "apply to a short progression": 0.25,
            "review": 0.15,
        }
        frag_text = "Add one chromatic passing tone between the root and 7th of a dominant chord. Play slowly with a swing feel."
        if gt.gt_list:
            frag_text += f" {gt.gt_list} Try adding a chromatic note between the root and 7th of the first chord."
        details = {
            "swing eighth-note feel": f"Play a simple scale on **{instrument}** with a relaxed swing feel. Accent beats 1 and 3. Count 1-and-2-and to feel the swing.",
            "simple bebop scale fragment": frag_text,
            "apply to a short progression": f"Use your bebop fragment over {gt.first_pair_chord_names or 'two chords'} from {target}. Keep the swing steady and resolve to a chord tone on beat 1.",
            "review": "Replay slowly. Does the passing tone resolve smoothly into a chord tone on the downbeat? Can you hear the swing?",
        }
    elif lvl == "advanced":
        weights = {
            "bebop scale through changes": 0.25,
            "enclosures and approach patterns": 0.25,
            "rhythmic displacement": 0.20,
            "song application with vocabulary": 0.20,
            "review": 0.10,
        }
        scale_text = f"Run the appropriate bebop scale (dominant or major) through the changes in {target}, keeping chord tones on downbeats."
        if gt.gt_list:
            scale_text += f" Target these guide tones on strong beats: {gt.gt_list}"
        encl_text = "Practice chromatic enclosures around guide tones: approach from above, below, and surround."
        if gt.first_vl:
            encl_text += f" Start by enclosing the 3rd of the second chord in {gt.first_pair_chord_names or 'the progression'}."
        details = {
            "bebop scale through changes": scale_text,
            "enclosures and approach patterns": encl_text,
            "rhythmic displacement": "Start the same bebop line on different beats to create rhythmic surprise. Keep harmonic accuracy: chord tones must still resolve on strong beats.",
            "song application with vocabulary": f"Improvise through {target} combining bebop scales, enclosures, and rhythmic variety. Record one chorus.",
            "review": "Listen to the recording. Where did chord tones miss strong beats? Where did enclosures feel forced?",
        }
    else:
        weights = {
            "bebop scale practice": 0.25,
            "chord-tone targeting on downbeats": 0.25,
            "simple enclosures": 0.25,
            "song application": 0.15,
            "review": 0.10,
        }
        ct_text = f"Over each chord in {target}, play eighth-note lines that land on a chord tone on beats 1 and 3."
        if gt.gt_list:
            ct_text += f" {gt.gt_list} Use these as your downbeat targets."
        encl_text = f"Approach a guide tone from a half step above and below before resolving. Practice on {gt.first_pair_chord_names or 'two or three chords'}."
        if gt.first_vl:
            encl_text += f" Try enclosing the 3rd at this voice-leading point: {gt.first_vl}."
        details = {
            "bebop scale practice": f"Play the bebop dominant scale on **{instrument}** in the song key. The extra chromatic note should place chord tones on downbeats.",
            "chord-tone targeting on downbeats": ct_text,
            "simple enclosures": encl_text,
            "song application": f"Apply bebop lines to {target} at a comfortable tempo. Stay with the swing feel.",
            "review": "Replay and check: do chord tones land on beats 1 and 3? Do enclosures resolve cleanly?",
        }
    return weights, details


def _dynamics_blocks(
    *,
    family: str,
    level: str,
    instrument: str,
    song: str,
    section: str,
) -> tuple[dict[str, float], dict[str, str]]:
    target = _song_section_phrase(song, section)
    lvl = _level_label(level) or "intermediate"

    if lvl == "beginner":
        weights = {
            "soft vs loud contrast": 0.30,
            "crescendo and decrescendo": 0.30,
            "apply dynamics to a passage": 0.25,
            "review": 0.15,
        }
        details = {
            "soft vs loud contrast": f"Play a simple phrase on **{instrument}** at piano (soft), then repeat at forte (loud); keep tone quality even.",
            "crescendo and decrescendo": "Play a 4-bar phrase getting gradually louder, then repeat getting softer; stay in time.",
            "apply dynamics to a passage": f"Choose one section of {target} and decide where to play soft and where to play louder.",
            "review": "Replay and check that volume changes were gradual, not sudden or jerky.",
        }
    elif lvl == "advanced":
        weights = {
            "dynamic shaping within phrases": 0.25,
            "subito dynamics and accent control": 0.25,
            "dynamic arc across the form": 0.25,
            "expressive application": 0.15,
            "review": 0.10,
        }
        details = {
            "dynamic shaping within phrases": f"Shape each 2–4 bar phrase in {target} with a subtle rise and fall; avoid flat dynamics.",
            "subito dynamics and accent control": "Practice sudden dynamic shifts (subito piano, sforzando) without losing tone quality or time.",
            "dynamic arc across the form": f"Plan and execute a dynamic arc across the full form of {target}: where does the climax land?",
            "expressive application": "Combine dynamic control with articulation and vibrato for musical expression.",
            "review": "Record a full pass and evaluate whether the dynamic plan was audible and musical.",
        }
    else:
        weights = {
            "dynamic range exploration": 0.25,
            "phrase-level dynamics": 0.25,
            "section contrast": 0.25,
            "song application": 0.15,
            "review": 0.10,
        }
        details = {
            "dynamic range exploration": f"Play the same passage on **{instrument}** at three levels: soft, medium, and full; keep tone even at each.",
            "phrase-level dynamics": f"Shape a 4-bar phrase from {target} with a small crescendo to the peak note, then ease back.",
            "section contrast": f"Play a verse softly and the chorus fuller in {target}; make the shift clear but not abrupt.",
            "song application": f"Apply your dynamic plan to a full section of {target}.",
            "review": "Replay and check that the dynamic differences are audible without distorting tone.",
        }
    return weights, details


def _focus_listen_and_progression(
    bucket: str, *,
    history: PracticeHistorySnapshot | None = None,
    chords: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    listen: list[str] = []
    progression: list[str] = [
        "Move to the next block only when the current one stays clean on most repetitions.",
    ]
    chord_names = ""
    if chords:
        unique: list[str] = []
        seen_ch: set[str] = set()
        for c in chords[:4]:
            cs = str(c).split("|")[0].strip()
            if cs and cs not in seen_ch:
                seen_ch.add(cs)
                unique.append(cs)
        chord_names = ", ".join(unique) if unique else ""
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
    elif bucket == "pentatonics":
        chord_ref = f" ({chord_names})" if chord_names else ""
        listen = [
            f"Pentatonic phrases resolve to a chord tone (root or 3rd) on beat 1 of each new chord{chord_ref}",
            "Smooth connection between scale positions without hesitation",
            "Rhythmic variety — not the same pattern every time",
            "Tone stays centered through all pentatonic notes",
        ]
        progression.append("Add tempo or new positions only after phrases consistently land on chord tones at changes.")
    elif bucket == "guide_tones":
        chord_ref = f" ({chord_names})" if chord_names else ""
        listen = [
            f"Can you identify the 3rd and 7th of each chord{chord_ref} without looking them up?",
            "Does the 7th of one chord resolve by step to the 3rd of the next?",
            "Does the guide-tone line sound like a melody when played alone?",
            "Can you maintain a steady pulse while playing guide tones through the progression?",
        ]
        progression.append("Add embellishment (passing tones, enclosures) only after the guide-tone line sounds like a melody on its own.")
    elif bucket == "bebop_phrasing":
        chord_ref = f" over {chord_names}" if chord_names else ""
        listen = [
            f"Do chord tones land on beats 1 and 3 of each measure{chord_ref}?",
            "Do chromatic passing tones resolve immediately to a chord tone?",
            "Does the swing feel stay even through longer eighth-note lines?",
            "Do enclosures resolve cleanly to the target guide tone?",
        ]
        progression.append("Add speed only after chromatic approaches resolve cleanly at a slow tempo.")
    elif bucket == "dynamics":
        listen = [
            "Clear contrast between soft and loud passages",
            "Gradual crescendo and decrescendo without tone loss",
            "Dynamic shape follows the musical phrase arc",
        ]
    elif bucket == "breath_endurance":
        listen = [
            "Steady air support through the full phrase",
            "Clean tone in the upper register without thinning",
            "Breath timing planned at natural phrase breaks",
        ]
    elif bucket == "ear_training":
        listen = [
            "Accurate pitch matching without guessing",
            "Intervals identified quickly and confidently",
            "Chord quality recognized by ear before checking",
        ]
    elif bucket == "guitar_rhythm":
        listen = [
            "Steady strum or pick pattern through chord changes",
            "Clean chord voicings without buzzing strings",
            "Accent pattern matches the groove feel",
        ]
        progression.append("Add chord variety only after the strum pattern stays steady through basic changes.")
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
    chords: list[str] | None = None,
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

    if bucket == "pentatonics":
        return _pentatonic_blocks(
            family=family,
            level=level,
            instrument=instrument,
            song=song,
            section=section,
            chords=chords or [],
        )

    if bucket == "guide_tones":
        return _guide_tone_blocks(
            family=family,
            level=level,
            instrument=instrument,
            song=song,
            section=section,
            chords=chords or [],
        )

    if bucket == "bebop_phrasing":
        return _bebop_phrasing_blocks(
            family=family,
            level=level,
            instrument=instrument,
            song=song,
            section=section,
            chords=chords or [],
        )

    if bucket == "dynamics":
        return _dynamics_blocks(
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
        "harmony": "harmony and voicing",
        "improvisation": "improvisation vocabulary",
        "phrasing": "phrasing and line shape",
        "fingerstyle": "fingerstyle technique",
        "bass_line": "bass-line development",
        "technique": f"{instrument} technique",
        "repertoire": "repertoire work",
        "pentatonics": "pentatonic scale application",
        "guide_tones": "guide-tone voice leading",
        "bebop_phrasing": "bebop phrasing and vocabulary",
        "dynamics": "dynamic control and expression",
        "breath_endurance": f"{instrument} breath and endurance",
        "ear_training": "ear training and recognition",
        "guitar_rhythm": "rhythm guitar and chord technique",
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
        if focus_phrase in {"harmony and voicing", "phrasing and line shape", "fingerstyle technique", "bass-line development"}:
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
    from music_coach_ami.musical_idea_knowledge import (
        _chart_sections_from_request,
        resolve_practice_section_target,
    )

    active_song = _clean(req.context.active_song_title)
    target = resolve_practice_section_target(
        req.raw_question or req.normalized_question,
        chart_sections=_chart_sections_from_request(req),
        active_section=str(req.context.active_section or ""),
    )
    if target.get("explicit") or target.get("source") == "explicit_question":
        section = _clean(target.get("section") or "")
        song = active_song or _clean(history.last_song)
        return song, section
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


def _extract_section_chords(req: CoachRequest, section: str) -> list[str]:
    """Pull chord symbols for the active section from chart context."""
    extra = req.context.extra if isinstance(req.context.extra, dict) else {}
    snap = extra.get("chart_snapshot") if isinstance(extra.get("chart_snapshot"), dict) else {}

    sections: dict = {}
    for key in ("chart_sections", "sections"):
        raw = snap.get(key) if snap else None
        if isinstance(raw, dict) and raw:
            sections = raw
            break
    if not sections:
        raw = extra.get("chart_sections")
        if isinstance(raw, dict):
            sections = raw

    if section and sections:
        sec_low = section.lower()
        for name, chords in sections.items():
            if str(name).lower() == sec_low and isinstance(chords, list):
                return [str(c) for c in chords if c][:16]

    active = list(snap.get("active_section_chords") or []) if snap else []
    if active:
        return [str(c) for c in active if c][:16]

    if sections:
        first_section = next(iter(sections.values()), [])
        if isinstance(first_section, list):
            return [str(c) for c in first_section if c][:16]
    return []


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

    section_chords = _extract_section_chords(req, section)

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

    weights, details = _instrument_blocks(
        family=family,
        focus=focus,
        level=level,
        instrument=instrument,
        history=history,
        song=song,
        section=section,
        chords=section_chords,
    )
    blocks = _allocate(minutes, weights)
    steps = []
    for label, mins in blocks.items():
        detail = details.get(label, "")
        line = f"**{mins} min** — {label}"
        if detail:
            line += f": {detail}"
        steps.append(line)

    listen, progression = _focus_listen_and_progression(bucket, history=history, chords=section_chords)

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
