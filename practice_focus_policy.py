"""Canonical Practice Focus coaching policy (SSOT).

This module defines **what a Practice Focus means** for coaching: category,
priorities, evaluation dimensions, exercises, and prompt language.

It does **not** own:
- the selected focus string (that stays in ``practice_setup_globals`` / ``focus``)
- song, Practice/Concert Key, Written Key, Guitar Shape
- backing source, generated Jam state, or Mission harmony

Pages should consume :func:`resolve_focus_profile` / overlays rather than
duplicating ``if focus == "Tone"`` trees.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

# ---------------------------------------------------------------------------
# Categories — coarse coaching buckets (not UI labels)
# ---------------------------------------------------------------------------

CATEGORY_TONE = "tone"
CATEGORY_TIMING = "timing"
CATEGORY_RHYTHM_GROOVE = "rhythm_groove"
CATEGORY_MELODY = "melody"
CATEGORY_HARMONY = "harmony"
CATEGORY_IMPROVISATION = "improvisation"
CATEGORY_TECHNIQUE = "technique"
CATEGORY_PHRASING = "phrasing"
CATEGORY_ARTICULATION = "articulation"
CATEGORY_DYNAMICS = "dynamics"
CATEGORY_EAR_TRAINING = "ear_training"
CATEGORY_GENERAL = "general"

ALL_CATEGORIES: tuple[str, ...] = (
    CATEGORY_TONE,
    CATEGORY_TIMING,
    CATEGORY_RHYTHM_GROOVE,
    CATEGORY_MELODY,
    CATEGORY_HARMONY,
    CATEGORY_IMPROVISATION,
    CATEGORY_TECHNIQUE,
    CATEGORY_PHRASING,
    CATEGORY_ARTICULATION,
    CATEGORY_DYNAMICS,
    CATEGORY_EAR_TRAINING,
    CATEGORY_GENERAL,
)

# Practice Log coarse taxonomy (existing FOCUS_AREAS). Missing historical
# Practice Focus must stay missing — this only maps a *known* label.
CATEGORY_TO_LOG_FOCUS_AREA: dict[str, str] = {
    CATEGORY_TONE: "tone",
    CATEGORY_TIMING: "timing/rhythm",
    CATEGORY_RHYTHM_GROOVE: "timing/rhythm",
    CATEGORY_MELODY: "melody",
    CATEGORY_HARMONY: "chords",
    CATEGORY_IMPROVISATION: "soloing/improv",
    CATEGORY_EAR_TRAINING: "ear training",
    CATEGORY_TECHNIQUE: "technical exercise",
    CATEGORY_PHRASING: "melody",
    CATEGORY_ARTICULATION: "tone",
    CATEGORY_DYNAMICS: "tone",
    CATEGORY_GENERAL: "general",
}

# Upload / mission metric ids that actually exist in mission_analysis.
# Policy lists preferences; callers must still intersect with available metrics.
_METRICS_RHYTHM = ("timing_groove", "rhythmic_diversity", "dynamic_contrast")
_METRICS_TONE = ("instrument_tone", "dynamic_contrast", "articulation")
_METRICS_MELODY = (
    "melodic_diversity_goal",
    "motif_development",
    "phrase_structure",
    "repetition_variation",
)
_METRICS_HARMONY = (
    "chord_tone_targeting",
    "guide_tones",
    "voice_leading",
    "deep_harmony",
)
_METRICS_IMPROV = (
    "motif_development",
    "chord_tone_targeting",
    "rhythmic_diversity",
    "space_silence",
)
_METRICS_PHRASING = (
    "phrase_structure",
    "space_silence",
    "call_response",
    "repetition_variation",
)
_METRICS_ARTICULATION = ("articulation", "timing_groove", "instrument_tone")
_METRICS_TIMING = ("timing_groove", "rhythmic_diversity", "space_silence")

STRUMMING_INSTRUMENTS: frozenset[str] = frozenset({"Guitar", "Ukulele", "Banjo", "Mandolin"})

SHARED_COACHING_FOCUSES: tuple[str, ...] = (
    "Timing",
    "Melody",
    "Harmony",
    "Improvisation",
    "Technique",
    "Phrasing",
    "Rhythm",
    "Tone",
)


@dataclass(frozen=True)
class FocusProfile:
    """Structured coaching policy for one Practice Focus label."""

    label: str
    category: str
    coaching_priorities: tuple[str, ...]
    evaluation_dimensions: tuple[str, ...]
    preferred_metric_ids: tuple[str, ...]
    score_keys: tuple[str, ...]
    exercise_categories: tuple[str, ...]
    practice_suggestions: tuple[str, ...]
    creative_emphasis: tuple[str, ...]
    backing_ideas: tuple[str, ...]
    terminology: tuple[str, ...]
    applicable_instruments: tuple[str, ...] = ()
    evidence_note: str = (
        "Increase coaching weight on these dimensions when evidence exists; "
        "do not fabricate metrics the signal cannot support. Mention major "
        "issues outside the focus when they are important. Do not hijack "
        "unrelated factual questions."
    )


def _profile(
    label: str,
    category: str,
    *,
    priorities: tuple[str, ...],
    evaluation: tuple[str, ...],
    metrics: tuple[str, ...],
    scores: tuple[str, ...],
    exercises: tuple[str, ...],
    practice: tuple[str, ...],
    creative: tuple[str, ...],
    backing: tuple[str, ...],
    terms: tuple[str, ...],
    instruments: tuple[str, ...] = (),
) -> FocusProfile:
    return FocusProfile(
        label=label,
        category=category,
        coaching_priorities=priorities,
        evaluation_dimensions=evaluation,
        preferred_metric_ids=metrics,
        score_keys=scores,
        exercise_categories=exercises,
        practice_suggestions=practice,
        creative_emphasis=creative,
        backing_ideas=backing,
        terminology=terms,
        applicable_instruments=instruments,
    )


# ---------------------------------------------------------------------------
# Canonical profiles by UI label
# ---------------------------------------------------------------------------

_PROFILES: dict[str, FocusProfile] = {
    "Strumming": _profile(
        "Strumming",
        CATEGORY_RHYTHM_GROOVE,
        instruments=("Guitar",),
        priorities=(
            "rhythmic consistency of the strumming hand",
            "up/down stroke patterns",
            "subdivision (especially eighth notes)",
            "groove and pocket",
            "accent patterns",
            "keeping the strumming hand moving through chord changes",
            "muting where the groove needs it",
            "pattern variations without losing time",
        ),
        evaluation=(
            "timing_consistency",
            "rhythmic_steadiness",
            "attack_consistency",
            "chord_transition_gaps",
            "groove",
            "accents",
            "pattern_stability",
        ),
        metrics=_METRICS_RHYTHM,
        scores=("timing", "groove", "technique"),
        exercises=(
            "isolated_strum_pattern",
            "downstrokes_then_upstrokes",
            "subdivision_drill",
            "accent_2_and_4",
            "chord_change_while_strumming",
            "gradual_bpm",
        ),
        practice=(
            "Isolate the strumming pattern on open strings or one chord before adding changes.",
            "Practice downstrokes first, then add upstrokes on a steady eighth-note grid.",
            "Accent beats 2 and 4 (or the song's backbeat) without stopping the hand.",
            "Practice chord transitions without pausing the strumming motion.",
            "Raise BPM only after the pattern stays even at the current tempo.",
        ),
        creative=(
            "Keep a fixed rhythmic strumming pattern while harmony changes.",
            "Maintain continuous eighth-note motion across the form.",
            "Vary accents while keeping the same chord progression.",
        ),
        backing=(
            "Choose a strumming pattern that matches the song's subdivision.",
            "Loop a short section and drill chord-change timing against the track.",
            "Try an easier then harder pattern at the same BPM.",
        ),
        terms=(
            "downstroke",
            "upstroke",
            "eighth-note grid",
            "backbeat",
            "muting",
            "groove",
        ),
    ),
    "Tone": _profile(
        "Tone",
        CATEGORY_TONE,
        priorities=(
            "consistent sound quality",
            "stable air or contact",
            "resonance",
            "register consistency",
            "attack and release",
            "controlled dynamics without pinching or collapsing the sound",
        ),
        evaluation=(
            "tone_quality",
            "sustain_consistency",
            "register_match",
            "attack_quality",
            "dynamic_control",
        ),
        metrics=_METRICS_TONE,
        scores=("tone", "pitch", "technique"),
        exercises=(
            "long_tones",
            "sustained_consistency",
            "crescendo_decrescendo",
            "register_matching",
            "tone_in_repertoire",
        ),
        practice=(
            "Start with long tones: stable pitch, even air or contact, no pinched sound.",
            "Match tone quality across registers before adding speed.",
            "Practice controlled crescendos and decrescendos on sustained notes.",
            "Carry the same tone target into a short phrase of the current song.",
        ),
        creative=(
            "Hold target tones with even sound across a progression.",
            "Shape dynamics of a motif without changing the notes.",
        ),
        backing=(
            "Sustain long notes over the progression and listen for even tone.",
            "Practice register matching on the same chord tones in different octaves.",
            "Add a dynamics exercise (pp to mf) over two-bar holds.",
        ),
        terms=("resonance", "embouchure", "air support", "attack", "sustain"),
    ),
    "Timing": _profile(
        "Timing",
        CATEGORY_TIMING,
        priorities=(
            "beat placement",
            "subdivision accuracy",
            "tempo stability",
            "rushing vs dragging",
            "rests and space that still sit in time",
        ),
        evaluation=(
            "timing_consistency",
            "tempo_stability",
            "subdivision_accuracy",
            "alignment",
        ),
        metrics=_METRICS_TIMING,
        scores=("timing", "groove"),
        exercises=(
            "metronome_on_beats",
            "subdivision_click",
            "silence_on_downbeats",
            "slow_then_up",
        ),
        practice=(
            "Practice with a metronome on every beat, then on 2 and 4 only.",
            "Speak or tap the subdivision before playing it.",
            "Loop a short passage and listen for rushing into chord changes or phrase peaks.",
            "Leave intentional rests that still land on the grid.",
        ),
        creative=(
            "Repeat a rhythmic motif exactly, then displace it by one eighth note.",
            "Use rests as part of the idea, not as hesitation.",
        ),
        backing=(
            "Set a metronomic target and a subdivision (quarters, eighths, triplets).",
            "Try a slightly slower BPM until placement is secure, then restore song tempo.",
        ),
        terms=("grid", "subdivision", "rushing", "dragging", "pocket"),
    ),
    "Melody": _profile(
        "Melody",
        CATEGORY_MELODY,
        priorities=(
            "melodic contour",
            "note choice",
            "phrasing of the line",
            "targeting chord tones",
            "motif development",
            "melodic rhythm",
        ),
        evaluation=(
            "melodic_contour",
            "target_tone_use",
            "motif_development",
            "phrase_shape",
        ),
        metrics=_METRICS_MELODY,
        scores=("musicality", "pitch", "timing"),
        exercises=(
            "sing_then_play",
            "motif_sequence",
            "chord_tone_targets",
            "contour_only",
        ),
        practice=(
            "Learn the melody slowly and name the contour (up, down, arch).",
            "Target chord tones on strong beats; use passing tones between them.",
            "Take a 2-bar motif and sequence it through the next chords.",
            "Vary rhythmic placement of the same pitches without losing the tune.",
        ),
        creative=(
            "Develop one motif instead of running scales.",
            "Aim for chord tones on downbeats; connect with stepwise motion.",
        ),
        backing=(
            "Play or sing the melody against the track, then ornament it.",
            "Leave space at phrase endings so the line can breathe.",
        ),
        terms=("contour", "motif", "target tone", "passing tone", "sequence"),
    ),
    "Harmony": _profile(
        "Harmony",
        CATEGORY_HARMONY,
        priorities=(
            "chord tones",
            "guide tones (3rds and 7ths)",
            "harmonic movement",
            "voice leading",
            "knowing what each chord is asking for",
        ),
        evaluation=(
            "chord_tone_accuracy",
            "guide_tone_use",
            "voice_leading",
            "harmonic_fit",
        ),
        metrics=_METRICS_HARMONY,
        scores=("musicality", "pitch"),
        exercises=(
            "chord_tone_only",
            "guide_tone_lines",
            "voice_leading_shifts",
            "name_the_changes",
        ),
        practice=(
            "Spell the chord tones of each harmony in the section.",
            "Practice 3rds and 7ths as a slow guide-tone line through the changes.",
            "Connect adjacent chords with the smallest voice-leading motion.",
            "On the song, pause on each new chord and resolve to a chord tone.",
        ),
        creative=(
            "Improvise using only chord tones, then add one tension.",
            "Keep a guide-tone line while the rhythm stays simple.",
        ),
        backing=(
            "Identify target chord tones on each change.",
            "Play a 2-note guide-tone challenge over the loop.",
        ),
        terms=("chord tone", "guide tone", "voice leading", "tension", "resolution"),
    ),
    "Improvisation": _profile(
        "Improvisation",
        CATEGORY_IMPROVISATION,
        priorities=(
            "motif development",
            "harmonic fit",
            "rhythmic ideas",
            "use of space",
            "telling a short musical story over the form",
        ),
        evaluation=(
            "motif_development",
            "harmonic_fit",
            "rhythmic_variety",
            "space",
        ),
        metrics=_METRICS_IMPROV,
        scores=("musicality", "timing", "groove"),
        exercises=(
            "one_motif_chorus",
            "call_response",
            "space_every_two_bars",
            "chord_tone_solo",
        ),
        practice=(
            "Improvise one chorus from a single 2-bar motif.",
            "Leave two beats of rest every other bar.",
            "Outline the changes with chord tones before adding scalar color.",
        ),
        creative=(
            "Keep the current Mission's concept; use Practice Focus as an extra dimension.",
            "Repeat and vary rather than inventing a new idea every bar.",
        ),
        backing=(
            "Loop one section and solo with a single rhythmic cell.",
            "Trade 2s or 4s with the track (play, then listen).",
        ),
        terms=("motif", "chorus", "changes", "space", "vocabulary"),
    ),
    "Phrasing": _profile(
        "Phrasing",
        CATEGORY_PHRASING,
        priorities=(
            "phrase length",
            "breathing or picking space",
            "question and answer shapes",
            "resolution",
            "repetition and variation",
        ),
        evaluation=("phrase_shape", "space", "resolution", "repetition_variation"),
        metrics=_METRICS_PHRASING,
        scores=("musicality", "timing"),
        exercises=("two_bar_phrases", "leave_space", "call_response", "resolve_on_one"),
        practice=(
            "Play 2-bar and 4-bar phrases with a clear ending.",
            "Leave space after each phrase instead of filling every beat.",
            "Answer a short idea with a related but varied reply.",
        ),
        creative=(
            "Shape question/answer phrases over the form.",
            "Resolve phrases toward chord tones on downbeats.",
        ),
        backing=(
            "2-bar / 4-bar phrase challenge against the loop.",
            "Leave-space challenge: rest the last two beats of every phrase.",
        ),
        terms=("phrase", "breath", "question/answer", "resolution"),
    ),
    "Articulation": _profile(
        "Articulation",
        CATEGORY_ARTICULATION,
        priorities=(
            "clear attacks",
            "consistent tonguing or picking",
            "legato vs staccato contrast",
            "entrances that speak on time",
        ),
        evaluation=("attack_consistency", "articulation_clarity", "timing_of_entrances"),
        metrics=_METRICS_ARTICULATION,
        scores=("technique", "timing", "tone"),
        exercises=("staccato_legato", "entrance_drill", "syllable_patterns"),
        practice=(
            "Isolate attacks on long tones, then on a simple melody.",
            "Alternate legato and staccato on the same pitches.",
            "Practice first notes of phrases until they speak cleanly in time.",
        ),
        creative=("Keep a rhythmic articulation pattern through a motif.",),
        backing=("Play the melody with contrasting articulation over the track.",),
        terms=("attack", "legato", "staccato", "tonguing", "picking"),
    ),
    "Technique": _profile(
        "Technique",
        CATEGORY_TECHNIQUE,
        priorities=(
            "efficient physical motion",
            "accuracy before speed",
            "instrument-specific mechanics",
            "relaxing tension",
        ),
        evaluation=("accuracy", "evenness", "tension"),
        metrics=("articulation", "timing_groove", "instrument_tone"),
        scores=("technique", "timing"),
        exercises=("slow_accuracy", "isolated_mechanic", "short_bursts"),
        practice=(
            "Slow the hard passage until it is clean, then add small tempo steps.",
            "Isolate the physical motion (hand, air, fingering) before combining.",
        ),
        creative=("Keep creative tasks technically simple enough to stay accurate.",),
        backing=("Loop the technically hard bar at reduced BPM.",),
        terms=("economy of motion", "accuracy", "tension"),
    ),
    "Rhythm": _profile(
        "Rhythm",
        CATEGORY_RHYTHM_GROOVE,
        priorities=(
            "steady pulse",
            "subdivision",
            "groove",
            "syncopation that still sits in time",
        ),
        evaluation=("timing_consistency", "groove", "subdivision_accuracy"),
        metrics=_METRICS_RHYTHM,
        scores=("timing", "groove"),
        exercises=("clap_subdivision", "metronome", "syncopation_cells"),
        practice=(
            "Lock a subdivision (quarters, eighths, sixteenths) before adding pitches.",
            "Practice the song's signature rhythm on one pitch or one chord.",
        ),
        creative=("Build a solo from one rhythmic cell.",),
        backing=("Match the track's groove; then add a slightly denser subdivision.",),
        terms=("pulse", "subdivision", "syncopation", "groove"),
    ),
    "Dynamics": _profile(
        "Dynamics",
        CATEGORY_DYNAMICS,
        priorities=("loud/soft control", "phrase-level shape", "accents"),
        evaluation=("dynamic_range", "accent_control"),
        metrics=("dynamic_contrast", "phrase_structure"),
        scores=("musicality", "tone"),
        exercises=("crescendo_decrescendo", "accent_map", "pp_to_ff"),
        practice=(
            "Play the phrase three times: soft, medium, then shaped (start soft, peak, release).",
        ),
        creative=("Keep pitches fixed and vary only dynamics.",),
        backing=("Ride a crescendo into the chorus against the track.",),
        terms=("crescendo", "decrescendo", "accent", "balance"),
    ),
    "Ear Training": _profile(
        "Ear Training",
        CATEGORY_EAR_TRAINING,
        priorities=("hearing intervals and chords", "matching pitch", "singing before playing"),
        evaluation=("pitch_accuracy", "recognition"),
        metrics=("chord_tone_targeting", "scale_connection"),
        scores=("pitch",),
        exercises=("sing_back", "interval_drill", "chord_quality_id"),
        practice=("Sing target notes, then play them. Identify I, IV, V by ear in the song.",),
        creative=("Call and response by ear over the form.",),
        backing=("Mute your part and sing chord roots, then play what you sang.",),
        terms=("interval", "chord quality", "matching pitch"),
    ),
}

# Additional existing UI labels → category + reuse a close canonical profile.
_LABEL_ALIASES: dict[str, str] = {
    "rhythm guitar": "Strumming",
    "chord transitions": "Harmony",
    "barre chords": "Technique",
    "fingerstyle": "Technique",
    "triads": "Harmony",
    "double stops": "Melody",
    "lead guitar": "Melody",
    "soloing": "Improvisation",
    "voicings": "Harmony",
    "left-hand patterns": "Technique",
    "comping": "Rhythm",
    "voice leading": "Harmony",
    "inversions": "Harmony",
    "reharmonization": "Harmony",
    "groove": "Rhythm",
    "pocket": "Timing",
    "root motion": "Harmony",
    "walking bass": "Improvisation",
    "syncopation": "Rhythm",
    "scales": "Technique",
    "bebop phrasing": "Phrasing",
    "breath support": "Tone",
    "breath control": "Tone",
    "guide tones": "Harmony",
    "jazz phrasing": "Phrasing",
    "endurance": "Technique",
    "range": "Technique",
    "pitch accuracy": "Ear Training",
    "emotional delivery": "Phrasing",
    "harmony singing": "Harmony",
    "vibrato": "Tone",
}


# Instrument-specific interpretation of the same category.
_INSTRUMENT_OVERLAYS: dict[tuple[str, str], tuple[str, ...]] = {
    ("Guitar", CATEGORY_RHYTHM_GROOVE): (
        "Keep the strumming or picking hand moving.",
        "Watch chord-transition gaps that stop the groove.",
        "Use muting and accents to define the pattern.",
    ),
    ("Guitar", CATEGORY_TONE): (
        "Focus on pick or finger attack, sustain, and unwanted string noise.",
        "Muting unused strings is part of guitar tone.",
    ),
    ("Guitar", CATEGORY_MELODY): (
        "Treat lead lines as sung phrases, not only scale runs.",
        "Target chord tones on the guitar neck you are actually using.",
    ),
    ("Saxophone", CATEGORY_TONE): (
        "Emphasize air support, stable embouchure, resonance, and register consistency.",
        "Avoid pinched tone; listen for even vibrato only after the core sound is stable.",
    ),
    ("Flute", CATEGORY_TONE): (
        "Air direction, aperture, and even tone across octaves.",
    ),
    ("Trumpet", CATEGORY_TONE): (
        "Center of pitch, efficiency of air, and consistent attacks without forcing.",
    ),
    ("Clarinet", CATEGORY_TONE): (
        "Even reed response, voicing, and matching chalumeau to clarion timbre.",
    ),
    ("Voice", CATEGORY_TONE): (
        "Breath, resonance, and vowel consistency more than volume.",
    ),
    ("Piano", CATEGORY_TECHNIQUE): (
        "Independence of hands; evenness of touch; voicing the melody above accompaniment.",
    ),
    ("Piano", CATEGORY_HARMONY): (
        "Left-hand roots vs inversions; right-hand chord tones and voice leading.",
    ),
    ("Bass", CATEGORY_RHYTHM_GROOVE): (
        "Lock with the imagined kick; consistent duration of notes in the pocket.",
    ),
    ("Saxophone", CATEGORY_ARTICULATION): (
        "Tonguing syllables (tu/du), clean starts, and even slurring.",
    ),
}


def canonical_instrument_label(instrument: str) -> str:
    """Map display names (Tenor Saxophone, Electric Guitar) to setup labels."""
    raw = str(instrument or "").strip()
    if not raw:
        return ""
    try:
        from practice_setup_controls import DEFAULT_INSTRUMENT_OPTIONS

        if raw in DEFAULT_INSTRUMENT_OPTIONS:
            return raw
    except ImportError:
        pass
    low = raw.lower()
    if "guitar" in low or "ukulele" in low or "banjo" in low or "mandolin" in low:
        return "Guitar"
    if "sax" in low:
        return "Saxophone"
    if "flute" in low:
        return "Flute"
    if "trumpet" in low or "cornet" in low or "flugel" in low:
        return "Trumpet"
    if "clarinet" in low:
        return "Clarinet"
    if any(x in low for x in ("voice", "vocal", "singer")):
        return "Voice"
    if "bass" in low:
        return "Bass"
    if any(x in low for x in ("piano", "keyboard", "keys")):
        return "Piano"
    return raw


def _norm_label(label: str) -> str:
    return " ".join(str(label or "").strip().lower().split())


def category_for_focus(focus: str) -> str:
    label = str(focus or "").strip()
    if not label:
        return CATEGORY_GENERAL
    profile = _PROFILES.get(label)
    if profile:
        return profile.category
    alias = _LABEL_ALIASES.get(_norm_label(label))
    if alias and alias in _PROFILES:
        return _PROFILES[alias].category
    low = _norm_label(label)
    if "strum" in low or "groove" in low or "pocket" in low or "syncop" in low:
        return CATEGORY_RHYTHM_GROOVE
    if "timing" in low or low == "rhythm" or "tempo" in low:
        return CATEGORY_TIMING
    if "tone" in low or "breath" in low or "embouchure" in low or "vibrato" in low:
        return CATEGORY_TONE
    if "articul" in low or "tongue" in low:
        return CATEGORY_ARTICULATION
    if "phras" in low:
        return CATEGORY_PHRASING
    if any(x in low for x in ("harmon", "chord", "voicing", "guide tone", "triad", "inversion")):
        return CATEGORY_HARMONY
    if any(x in low for x in ("melod", "lead", "double stop")):
        return CATEGORY_MELODY
    if any(x in low for x in ("improv", "solo", "walking")):
        return CATEGORY_IMPROVISATION
    if "ear" in low or "pitch accuracy" in low:
        return CATEGORY_EAR_TRAINING
    if "dynamic" in low:
        return CATEGORY_DYNAMICS
    if any(x in low for x in ("technique", "fingerstyle", "barre", "endurance", "range", "scale")):
        return CATEGORY_TECHNIQUE
    return CATEGORY_GENERAL


def coarse_log_focus_area(focus: str) -> str | None:
    """Map a known Practice Focus label onto Practice Log FOCUS_AREAS.

    Returns None when *focus* is empty so callers do not invent a historical value.
    """
    label = str(focus or "").strip()
    if not label:
        return None
    category = category_for_focus(label)
    return CATEGORY_TO_LOG_FOCUS_AREA.get(category, "general")


def focus_is_compatible(instrument: str, focus: str) -> bool:
    """True when *focus* is in the instrument's option list."""
    label = str(focus or "").strip()
    if not label:
        return False
    try:
        from practice_setup_controls import focus_options_for_instrument

        opts = focus_options_for_instrument(canonical_instrument_label(instrument) or instrument)
    except ImportError:
        opts = []
    return label in opts


def resolve_compatible_focus(instrument: str, candidate: Any) -> str:
    """Keep *candidate* if valid for *instrument*; otherwise the instrument default.

    Default is the first option for that instrument (Guitar → Strumming, Sax → Tone).
    This is deterministic and avoids silently carrying Guitar-only focuses onto winds.
    """
    try:
        from practice_setup_globals import valid_focus_for

        return valid_focus_for(canonical_instrument_label(instrument) or instrument, candidate)
    except ImportError:
        from practice_setup_controls import focus_options_for_instrument

        opts = focus_options_for_instrument(canonical_instrument_label(instrument) or instrument)
        raw = str(candidate or "").strip()
        if opts and raw not in opts:
            return opts[0]
        return raw or (opts[0] if opts else "")


def _base_profile_for_label(focus: str) -> FocusProfile:
    label = str(focus or "").strip()
    if label in _PROFILES:
        return _PROFILES[label]
    alias = _LABEL_ALIASES.get(_norm_label(label))
    if alias and alias in _PROFILES:
        aliased = _PROFILES[alias]
        return replace(aliased, label=label or aliased.label)
    category = category_for_focus(label)
    # Fall back to a canonical profile that shares the category.
    for candidate in _PROFILES.values():
        if candidate.category == category:
            return replace(candidate, label=label or candidate.label)
    return _profile(
        label or "General",
        CATEGORY_GENERAL,
        priorities=("balanced practice across sound, time, and the current song",),
        evaluation=("overall_musicality",),
        metrics=("timing_groove", "phrase_structure"),
        scores=("musicality", "timing"),
        exercises=("song_section", "slow_practice"),
        practice=("Work the current song slowly with a clear small goal.",),
        creative=("Keep the Mission or tool purpose; add focus only when it fits.",),
        backing=("Use the track to support a specific, small practice goal.",),
        terms=("practice goal",),
    )


def resolve_focus_profile(instrument: str, focus: str) -> FocusProfile:
    """Return the coaching profile for this instrument + Practice Focus."""
    inst = canonical_instrument_label(instrument)
    profile = _base_profile_for_label(focus)
    overlay = _INSTRUMENT_OVERLAYS.get((inst, profile.category), ())
    if overlay:
        profile = replace(
            profile,
            coaching_priorities=overlay + profile.coaching_priorities,
            practice_suggestions=overlay + profile.practice_suggestions,
        )
    return profile


def format_focus_prompt_block(
    instrument: str,
    focus: str,
    *,
    role: str = "ami",
) -> str:
    """Reusable AI context: bias toward the focus without imprisoning the answer."""
    inst = canonical_instrument_label(instrument) or str(instrument or "instrument").strip()
    label = str(focus or "").strip()
    if not label:
        return ""
    profile = resolve_focus_profile(inst, label)
    priorities = "; ".join(profile.coaching_priorities[:6])
    if role == "analysis":
        use = (
            "For this evaluation, increase weight and coaching priority on the "
            "focus dimensions. Still report serious problems outside the focus. "
            "Do not claim metrics the audio cannot support."
        )
    elif role == "history":
        use = (
            "These records capture the Practice Focus that was active at the "
            "time of practice. Do not reinterpret old sessions using a later "
            "current focus. If current focus differs, say so explicitly."
        )
    else:
        use = (
            "When the user asks what to practice, how to practice a song, or "
            "for a routine, strongly use this focus. For unrelated factual "
            "questions, answer directly; connect to the focus only if it truly helps. "
            "Do not start every sentence with the focus."
        )
    return (
        f"Practice Focus coaching context (bias, not a prison):\n"
        f"- Instrument: {inst}\n"
        f"- Current Practice Focus: {profile.label}\n"
        f"- Category: {profile.category}\n"
        f"- Increased attention: {priorities}\n"
        f"- {use}\n"
        f"- {profile.evidence_note}"
    )


def profiles_differ_meaningfully(left: FocusProfile, right: FocusProfile) -> bool:
    """Acceptance helper: two focuses should not collapse to the same coaching."""
    if left.category != right.category:
        return True
    if left.preferred_metric_ids != right.preferred_metric_ids:
        return True
    if left.coaching_priorities[:3] != right.coaching_priorities[:3]:
        return True
    return left.practice_suggestions[:2] != right.practice_suggestions[:2]


def profile_as_dict(profile: FocusProfile) -> dict[str, Any]:
    return {
        "label": profile.label,
        "category": profile.category,
        "coaching_priorities": list(profile.coaching_priorities),
        "evaluation_dimensions": list(profile.evaluation_dimensions),
        "preferred_metric_ids": list(profile.preferred_metric_ids),
        "score_keys": list(profile.score_keys),
        "exercise_categories": list(profile.exercise_categories),
        "practice_suggestions": list(profile.practice_suggestions),
        "creative_emphasis": list(profile.creative_emphasis),
        "backing_ideas": list(profile.backing_ideas),
        "terminology": list(profile.terminology),
        "applicable_instruments": list(profile.applicable_instruments),
        "evidence_note": profile.evidence_note,
    }


def append_shared_coaching_focuses(options: list[str] | tuple[str, ...]) -> list[str]:
    """Add cross-instrument coaching focuses without changing the default (first) option."""
    out = [str(x) for x in options]
    for label in SHARED_COACHING_FOCUSES:
        if label not in out:
            out.append(label)
    return out
