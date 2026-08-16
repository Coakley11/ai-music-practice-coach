"""Shared Practice Focus coaching for AMI and the Practice page.

Consumes ``practice_focus_policy`` / ``PracticeFocusContext``. Does not own
song, keys, backing, Jam, or Mission harmony.
"""

from __future__ import annotations

from typing import Any, Mapping

from practice_focus_policy import (
    CATEGORY_ARTICULATION,
    CATEGORY_DYNAMICS,
    CATEGORY_EAR_TRAINING,
    CATEGORY_GENERAL,
    CATEGORY_HARMONY,
    CATEGORY_IMPROVISATION,
    CATEGORY_MELODY,
    CATEGORY_PHRASING,
    CATEGORY_RHYTHM_GROOVE,
    CATEGORY_TECHNIQUE,
    CATEGORY_TIMING,
    CATEGORY_TONE,
    _INSTRUMENT_OVERLAYS,
    canonical_instrument_label,
    category_for_focus,
    format_focus_prompt_block,
    resolve_focus_profile,
)

_CATEGORY_TO_AMI_BUCKET: dict[str, str] = {
    CATEGORY_TONE: "tone",
    CATEGORY_TIMING: "timing",
    CATEGORY_RHYTHM_GROOVE: "rhythm_groove",
    CATEGORY_MELODY: "melody",
    CATEGORY_HARMONY: "harmony",
    CATEGORY_IMPROVISATION: "improvisation",
    CATEGORY_TECHNIQUE: "technique",
    CATEGORY_PHRASING: "phrasing",
    CATEGORY_ARTICULATION: "articulation",
    CATEGORY_DYNAMICS: "dynamics",
    CATEGORY_EAR_TRAINING: "ear_training",
    CATEGORY_GENERAL: "general",
}

_CATEGORY_TO_PAGE_KIND: dict[str, str] = {
    CATEGORY_TONE: "Tone",
    CATEGORY_TIMING: "Timing",
    CATEGORY_RHYTHM_GROOVE: "Rhythm",
    CATEGORY_MELODY: "Melody",
    CATEGORY_HARMONY: "Harmony",
    CATEGORY_IMPROVISATION: "Improvisation",
    CATEGORY_TECHNIQUE: "Technique",
    CATEGORY_PHRASING: "Phrasing",
    CATEGORY_ARTICULATION: "Articulation",
    CATEGORY_DYNAMICS: "Dynamics",
    CATEGORY_EAR_TRAINING: "Ear Training",
    CATEGORY_GENERAL: "Technique",
}

_SPECIALIZED_AMI_BUCKETS = frozenset({"fingerstyle", "bass_line"})


def ami_focus_bucket(focus: str) -> str:
    """Map a Practice Focus label onto AMI plan buckets."""
    low = str(focus or "").strip().lower()
    if "fingerstyle" in low or "finger style" in low:
        return "fingerstyle"
    if "bass line" in low or "bass-line" in low or "walking bass" in low:
        return "bass_line"
    return _CATEGORY_TO_AMI_BUCKET.get(category_for_focus(focus), "general")


def practice_page_kind(focus: str) -> str:
    """Practice-page drill family. Unknown labels fall back to Technique."""
    low = str(focus or "").strip().lower()
    if "fingerstyle" in low:
        return "Technique"
    return _CATEGORY_TO_PAGE_KIND.get(category_for_focus(focus), "Technique")


def should_prefer_policy_plan(focus: str) -> bool:
    """True when AMI should use policy-built blocks instead of legacy generics."""
    bucket = ami_focus_bucket(focus)
    if bucket in _SPECIALIZED_AMI_BUCKETS:
        return False
    return bucket not in {"", "general"}


def context_prompt_block(instrument: str, focus: str, *, role: str = "ami") -> str:
    return format_focus_prompt_block(instrument, focus, role=role)


def _song_apply_line(song: str, section: str) -> str:
    song_title = str(song or "").strip()
    sec = str(section or "").strip()
    if sec and sec.lower() in {"full song", "full", "all", "song", "entire song"}:
        sec = ""
    if sec and song_title:
        return f"Apply this in the **{sec}** of **{song_title}**."
    if song_title:
        return f"Apply this on **{song_title}**."
    return "Apply this to a short phrase from your current song or a backing loop."


def _pick_suggestion(suggestions: tuple[str, ...] | list[str], *needles: str, fallback: str = "") -> str:
    items = [str(s).strip() for s in suggestions if str(s).strip()]
    for needle in needles:
        n = needle.lower()
        for s in items:
            if n in s.lower():
                return s
    if items:
        return items[0]
    return fallback


def timed_practice_blocks(
    instrument: str,
    focus: str,
    *,
    song: str = "",
    section: str = "",
    level: str = "",
) -> tuple[dict[str, float], dict[str, str]]:
    """Weight map + detail text for a timed AMI practice plan."""
    profile = resolve_focus_profile(instrument, focus)
    apply_line = _song_apply_line(song, section)
    suggestions = profile.practice_suggestions
    cat = profile.category
    inst = str(instrument or "your instrument")

    if cat == CATEGORY_RHYTHM_GROOVE:
        weights = {
            "isolated pattern": 0.18,
            "subdivision & accents": 0.22,
            "chord changes without stopping": 0.25,
            "song / backing application": 0.22,
            "review": 0.13,
        }
        details = {
            "isolated pattern": _pick_suggestion(
                suggestions, "isolate", "downstroke", "pattern",
                fallback="Isolate the rhythmic pattern on one chord or muted strings.",
            ),
            "subdivision & accents": _pick_suggestion(
                suggestions, "accent", "eighth", "subdivision",
                fallback="Lock a steady eighth-note grid; add accents only after the hand stays even.",
            ),
            "chord changes without stopping": _pick_suggestion(
                suggestions, "chord", "transition", "hand moving",
                fallback="Change chords without pausing the strumming or groove hand.",
            ),
            "song / backing application": apply_line + " Keep the pattern through the form.",
            "review": "Play one short take and notice where the groove breaks.",
        }
        return weights, details

    if cat == CATEGORY_TIMING:
        weights = {
            "metronome groove": 0.28,
            "subdivision placement": 0.27,
            "section loop": 0.28,
            "review": 0.17,
        }
        details = {
            "metronome groove": _pick_suggestion(
                suggestions, "metronome", "beat",
                fallback="Practice with a metronome on every beat, then on 2 and 4 only.",
            ),
            "subdivision placement": _pick_suggestion(
                suggestions, "subdivision", "rush", "drag",
                fallback="Speak or tap the subdivision before playing it; listen for rushing or dragging.",
            ),
            "section loop": apply_line + " Loop a short passage until placement stays reliable.",
            "review": "Notice where time wobbles — usually into peaks or chord changes.",
        }
        return weights, details

    if cat == CATEGORY_TONE:
        weights = {
            "long tones": 0.28,
            "register consistency": 0.22,
            "dynamics & attacks": 0.18,
            "repertoire application": 0.22,
            "review": 0.10,
        }
        details = {
            "long tones": _pick_suggestion(
                suggestions, "long tone", "air", "embouchure", "sustain",
                fallback=f"Play long tones on **{inst}**: stable sound, no pinched or collapsed tone.",
            ),
            "register consistency": _pick_suggestion(
                suggestions, "register",
                fallback="Match tone quality across registers before adding speed.",
            ),
            "dynamics & attacks": _pick_suggestion(
                suggestions, "crescendo", "attack", "dynamic",
                fallback="Practice controlled crescendos/decrescendos and even attacks.",
            ),
            "repertoire application": apply_line + " Keep the same tone target in the music.",
            "review": "Name one tone win and one register or attack still to stabilize.",
        }
        return weights, details

    if cat == CATEGORY_ARTICULATION:
        weights = {
            "warm-up tone centering": 0.15,
            "single-note tonguing": 0.30,
            "slur/tongue contrast": 0.25,
            "musical phrase application": 0.20,
            "review": 0.10,
        }
        details = {
            "warm-up tone centering": f"Play a few comfortable notes on **{inst}** with steady sound before adding articulation.",
            "single-note tonguing": _pick_suggestion(
                suggestions, "attack", "tongue", "staccato",
                fallback="Repeat clean attacks on one pitch; keep each start identical.",
            ),
            "slur/tongue contrast": _pick_suggestion(
                suggestions, "legato", "staccato",
                fallback="Alternate legato and tongued (or picked) versions of the same pitches.",
            ),
            "musical phrase application": apply_line + " Use one articulation pattern through the phrase.",
            "review": "Check that entrances speak on time without thinning the sound.",
        }
        return weights, details

    if cat == CATEGORY_PHRASING:
        weights = {
            "phrase length": 0.25,
            "breathing / space": 0.25,
            "question and answer": 0.25,
            "song application": 0.15,
            "review": 0.10,
        }
        details = {
            "phrase length": _pick_suggestion(
                suggestions, "2-bar", "4-bar", "phrase",
                fallback="Play 2-bar and 4-bar phrases with a clear ending.",
            ),
            "breathing / space": _pick_suggestion(
                suggestions, "space", "breath",
                fallback="Leave space after each phrase instead of filling every beat.",
            ),
            "question and answer": _pick_suggestion(
                suggestions, "question", "answer",
                fallback="Answer a short idea with a related but varied reply.",
            ),
            "song application": apply_line,
            "review": "Listen for sentence shape: start, direction, and resolution.",
        }
        return weights, details

    if cat == CATEGORY_HARMONY:
        weights = {
            "chord tones": 0.28,
            "guide tones / voice leading": 0.30,
            "section application": 0.27,
            "review": 0.15,
        }
        details = {
            "chord tones": _pick_suggestion(
                suggestions, "chord tone", "spell",
                fallback="Spell the chord tones of each harmony in the section.",
            ),
            "guide tones / voice leading": _pick_suggestion(
                suggestions, "guide", "voice-leading", "voice leading",
                fallback="Practice 3rds and 7ths as a slow guide-tone line; use the smallest motion between chords.",
            ),
            "section application": apply_line + " Pause on each new chord and resolve to a chord tone.",
            "review": "Name the function of the hardest change and whether the line resolved.",
        }
        return weights, details

    if cat == CATEGORY_MELODY:
        weights = {
            "contour": 0.25,
            "target tones": 0.25,
            "motif development": 0.25,
            "song application": 0.15,
            "review": 0.10,
        }
        details = {
            "contour": _pick_suggestion(
                suggestions, "contour",
                fallback="Learn the line slowly and name the contour (up, down, arch).",
            ),
            "target tones": _pick_suggestion(
                suggestions, "chord tone", "target",
                fallback="Target chord tones on strong beats; use passing tones between them.",
            ),
            "motif development": _pick_suggestion(
                suggestions, "motif", "sequence",
                fallback="Take a 2-bar motif and sequence it through the next chords.",
            ),
            "song application": apply_line,
            "review": "Keep the tune recognizable even when you ornament it.",
        }
        return weights, details

    if cat == CATEGORY_IMPROVISATION:
        weights = {
            "one motif": 0.30,
            "harmonic fit": 0.25,
            "space": 0.20,
            "chorus application": 0.15,
            "review": 0.10,
        }
        details = {
            "one motif": _pick_suggestion(
                suggestions, "motif",
                fallback="Improvise from a single 2-bar motif instead of new ideas every bar.",
            ),
            "harmonic fit": _pick_suggestion(
                suggestions, "chord tone",
                fallback="Outline the changes with chord tones before adding scalar color.",
            ),
            "space": _pick_suggestion(
                suggestions, "rest", "space",
                fallback="Leave two beats of rest every other bar.",
            ),
            "chorus application": apply_line,
            "review": "Ask whether the chorus told one story or several unfinished ones.",
        }
        return weights, details

    # Generic / unknown / technique / dynamics / ear — still usable, not instrument-nonsensical.
    weights = {
        "warmup": 0.20,
        "focused drill": 0.35,
        "song application": 0.30,
        "review": 0.15,
    }
    first = suggestions[0] if suggestions else f"Work a small, clear goal on **{inst}** at a controlled tempo."
    second = suggestions[1] if len(suggestions) > 1 else "Isolate the hardest motion before combining it with the song."
    details = {
        "warmup": first,
        "focused drill": second,
        "song application": apply_line,
        "review": "Log one thing that improved and one thing still unstable.",
    }
    return weights, details


def listen_and_progression_for_focus(instrument: str, focus: str) -> tuple[list[str], list[str]]:
    profile = resolve_focus_profile(instrument, focus)
    cat = profile.category
    listen_by_cat: dict[str, list[str]] = {
        CATEGORY_RHYTHM_GROOVE: [
            "The strumming or groove hand keeps moving through changes",
            "Subdivision stays even; accents land where you intended",
            "Chord-transition gaps do not stop the pattern",
        ],
        CATEGORY_TIMING: [
            "Beat 1 is obvious and unhurried",
            "Subdivision stays even; watch rushing into peaks or changes",
            "Rests still sit on the grid",
        ],
        CATEGORY_TONE: [
            "Centered, stable sound without pinching or collapsing",
            "Register matches — same quality high and low",
            "Attacks and releases stay consistent",
        ],
        CATEGORY_ARTICULATION: [
            "Each attack speaks cleanly and on time",
            "Legato and separated notes are clearly different",
            "Tone does not thin when articulation gets busier",
        ],
        CATEGORY_PHRASING: [
            "Phrases have a beginning, direction, and ending",
            "There is audible space / breath between ideas",
            "Dynamics help the sentence, not random volume",
        ],
        CATEGORY_HARMONY: [
            "Chord tones land on strong beats",
            "Guide tones (3rds/7ths) connect smoothly",
            "You can name what the next chord is asking for",
        ],
        CATEGORY_MELODY: [
            "The contour is intentional",
            "Target tones resolve the phrase",
            "A motif repeats or sequences instead of random notes",
        ],
        CATEGORY_IMPROVISATION: [
            "One idea develops instead of a new idea every bar",
            "Harmony is outlined, not ignored",
            "Space is part of the line",
        ],
    }
    listen = listen_by_cat.get(cat, ["Musical shape over speed", "Clean execution at a controlled tempo"])
    progression = [
        "Move to the next block only when the current one stays clean on most repetitions.",
    ]
    if cat == CATEGORY_TIMING:
        progression.append("Increase tempo only after placement feels reliable.")
    elif cat == CATEGORY_RHYTHM_GROOVE:
        progression.append("Add upstrokes, accents, or tempo only after the hand stays continuous.")
    elif cat == CATEGORY_TONE:
        progression.append("Add range or repertoire only when the core sound stays centered.")
    elif cat == CATEGORY_PHRASING:
        progression.append("Extend phrase length only when 2-bar fragments stay shaped.")
    return listen, progression


def practice_page_focus_lines(
    instrument: str,
    focus: str,
    *,
    first_chord: str = "",
    second_chord: str = "",
    chord_path: str = "",
    section_name: str = "",
) -> list[str]:
    """Three Practice-page drills from the policy, tied to the current section chords."""
    profile = resolve_focus_profile(instrument, focus)
    material = ""
    if first_chord and second_chord:
        material = f" Use **{first_chord} -> {second_chord}**"
        if section_name:
            material += f" in **{section_name}**"
        if chord_path:
            material += f" ({chord_path})"
        material += "."
    elif chord_path:
        material = f" Loop **{chord_path}**."

    overlay = [
        str(s).strip()
        for s in _INSTRUMENT_OVERLAYS.get(
            (canonical_instrument_label(instrument), profile.category), ()
        )
        if str(s).strip()
    ]
    canonical = []
    overlay_set = set(overlay)
    for suggestion in profile.practice_suggestions:
        text = str(suggestion).strip()
        if text and text not in overlay_set and text not in canonical:
            canonical.append(text)
    mixed: list[str] = []
    if overlay:
        mixed.append(overlay[0])
    mixed.extend(canonical)

    lines: list[str] = []
    for suggestion in mixed[:3]:
        text = str(suggestion).rstrip(".")
        lines.append(f"{text}.{material}" if material else f"{text}.")
    while len(lines) < 3:
        lines.append(
            f"Keep **{profile.label}** as the main goal while you loop the section{material}"
        )
    return lines[:3]


def practice_page_watch_for(instrument: str, focus: str) -> list[str]:
    listen, _prog = listen_and_progression_for_focus(instrument, focus)
    return listen[:3]


def context_from_session_or_labels(
    session_state: Mapping[str, Any] | None,
    *,
    instrument: str = "",
    focus: str = "",
):
    """Resolve live context when a session exists; otherwise build from labels."""
    from practice_focus_context import resolve_practice_focus_context

    if session_state is not None:
        return resolve_practice_focus_context(session_state)
    return resolve_practice_focus_context(
        {"instrument": instrument or "Piano", "focus": focus or "", "level": "Intermediate"}
    )
