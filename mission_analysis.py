"""Improvisation mission scoring from recordings (librosa heuristics + coach copy)."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np

from improvisation_motif import chord_tone_names
from music_theory import CHROMATIC, normalize_root, split_chord

try:
    import librosa
except ImportError:
    librosa = None  # type: ignore[assignment]

MISSION_HISTORY_FILE = Path("mission_analysis_history.json")

# ---------------------------------------------------------------------------
# Mission catalog
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissionGoal:
    id: str
    label: str
    weights: dict[str, float]
    legacy_labels: tuple[str, ...] = ()


def _w(**pairs: float) -> dict[str, float]:
    total = sum(pairs.values()) or 1.0
    return {k: v / total for k, v in pairs.items()}


MISSION_GOALS: tuple[MissionGoal, ...] = (
    MissionGoal("one_motif", "Develop one motif", _w(motif_consistency=0.45, motif_transformation=0.2, melodic_diversity=0.15, repetition_variation=0.2)),
    MissionGoal("rhythmic_diversity", "Rhythmic diversity", _w(rhythmic_diversity=0.5, rhythmic_syncopation=0.3, phrase_pacing=0.2)),
    MissionGoal("motif_development", "Motif development", _w(motif_consistency=0.35, motif_transformation=0.35, repetition_variation=0.2, phrase_contour_variety=0.1)),
    MissionGoal("phrase_structure", "Phrase structure", _w(phrase_pacing=0.4, phrase_contour_variety=0.35, space_rests=0.25)),
    MissionGoal("melodic_diversity_goal", "Melodic diversity", _w(melodic_diversity=0.65, phrase_contour_variety=0.35)),
    MissionGoal("chord_tone_targeting", "Chord-tone targeting", _w(chord_tone_accuracy=0.5, landing_note_quality=0.3, resolution_strength=0.2)),
    MissionGoal("tension_release", "Tension and release", _w(tension_release_balance=0.45, melodic_diversity=0.2, resolution_strength=0.2, phrase_pacing=0.15)),
    MissionGoal("phrasing", "Phrasing", _w(phrase_pacing=0.35, phrase_contour_variety=0.3, space_rests=0.2, landing_note_quality=0.15)),
    MissionGoal("space_silence", "Use of space/rests", _w(space_rests=0.55, phrase_pacing=0.25, dynamic_contrast=0.2)),
    MissionGoal("dynamic_contrast", "Dynamics", _w(dynamic_contrast=0.6, phrase_pacing=0.2, musical_expression=0.2)),
    MissionGoal("pentatonic_focus", "Pentatonic focus", _w(pentatonic_adherence=0.55, scale_adherence=0.25, melodic_diversity=0.2)),
    # Scale/mode usage is scored from tonal/harmonic membership evidence only.
    # Melodic diversity and phrase-contour variety are separate criteria and must
    # not dilute this score when they are low.
    MissionGoal(
        "scale_connection",
        "Scale/mode usage",
        _w(scale_adherence=0.75, chord_tone_accuracy=0.15, guide_tone_usage=0.10),
    ),
    MissionGoal("voice_leading", "Voice leading", _w(voice_leading_smoothness=0.5, resolution_strength=0.25, chord_tone_accuracy=0.25)),
    MissionGoal("repetition_variation", "Repetition and variation", _w(repetition_variation=0.45, motif_transformation=0.35, rhythmic_diversity=0.2)),
    MissionGoal("guide_tones", "Guide-tone targeting", _w(guide_tone_usage=0.55, landing_note_quality=0.3, resolution_strength=0.15)),
    MissionGoal("rhythmic_displacement", "Rhythmic displacement", _w(rhythmic_syncopation=0.45, rhythmic_diversity=0.35, groove_consistency=0.2)),
    MissionGoal("bebop_phrasing", "Bebop phrasing", _w(rhythmic_syncopation=0.3, phrase_contour_variety=0.25, tension_release_balance=0.25, chromatic_motion=0.2)),
    MissionGoal("call_response", "Call and response", _w(phrase_pacing=0.35, space_rests=0.3, repetition_variation=0.35)),
    MissionGoal("deep_harmony", "Deep harmony awareness", _w(chord_tone_accuracy=0.35, guide_tone_usage=0.3, voice_leading_smoothness=0.2, scale_adherence=0.15)),
    MissionGoal("timing_groove", "Timing/groove", _w(groove_consistency=0.45, timing_stability=0.4, landing_note_quality=0.15)),
    MissionGoal("articulation", "Articulation", _w(articulation=0.55, rhythmic_diversity=0.25, groove_consistency=0.2)),
    MissionGoal("instrument_tone", "Instrument tone", _w(instrument_tone=0.55, musical_expression=0.25, melodic_diversity=0.2)),
    MissionGoal(
        "mission_completion",
        "Mission completion",
        _w(musical_expression=0.3, motif_consistency=0.25, chord_tone_accuracy=0.25, groove_consistency=0.2),
    ),
    MissionGoal(
        "custom",
        "Custom goal",
        _w(musical_expression=0.25, phrase_pacing=0.25, melodic_diversity=0.25, groove_consistency=0.25),
    ),
)

MISSION_BY_ID: dict[str, MissionGoal] = {m.id: m for m in MISSION_GOALS}
MISSION_LABELS: list[str] = [m.label for m in MISSION_GOALS if m.id != "custom"]

# User-facing multiselect order (Improvisation Intelligence + Upload Analysis)
AI_IMPROV_METRIC_IDS: tuple[str, ...] = (
    "motif_development",
    "phrase_structure",
    "rhythmic_diversity",
    "melodic_diversity_goal",
    "chord_tone_targeting",
    "guide_tones",
    "tension_release",
    "space_silence",
    "call_response",
    "repetition_variation",
    "voice_leading",
    "scale_connection",
    "deep_harmony",
    "dynamic_contrast",
    "timing_groove",
    "articulation",
    "instrument_tone",
    "mission_completion",
)

AI_IMPROV_METRIC_LABELS: list[str] = [
    MISSION_BY_ID[mid].label for mid in AI_IMPROV_METRIC_IDS if mid in MISSION_BY_ID
]

LEGACY_MISSION_TO_IDS: dict[str, list[str]] = {
    "Improvise using only chord tones": ["chord_tone_targeting"],
    "Use only 5 notes in one register": ["pentatonic_focus", "one_motif"],
    "Focus on rhythm over note choice": ["rhythmic_diversity", "rhythmic_displacement"],
    "Create tension on dominant chords": ["tension_release"],
    "Develop one motif for the entire solo": ["one_motif", "motif_development"],
    "Use silence intentionally (rest every 2 bars)": ["space_silence", "phrasing"],
    "Resolve every phrase on beat 1": ["guide_tones", "chord_tone_targeting"],
    "No repeated rhythmic pattern twice in a row": ["rhythmic_diversity", "repetition_variation"],
    "Target only guide tones (3rds & 7ths)": ["guide_tones"],
    "Play one chorus without scalar runs": ["chord_tone_targeting", "phrasing"],
}


def mission_ids_from_legacy(label: str) -> list[str]:
    return list(LEGACY_MISSION_TO_IDS.get(label, []))


def resolve_selected_mission_ids(
    session_state: dict,
    *,
    include_creative: bool = True,
) -> list[str]:
    """Merge AI metric picks, upload-page picks, and optional Creative Lab mission."""
    ids: list[str] = []

    def _add(raw: Any) -> None:
        if not isinstance(raw, list):
            return
        for x in raw:
            mid = str(x)
            if mid in MISSION_BY_ID and mid != "custom" and mid not in ids:
                ids.append(mid)

    _add(session_state.get("analysis_inherited_ai_metric_ids"))
    _add(session_state.get("analysis_additional_take_metric_ids"))
    _add(session_state.get("analysis_effective_metric_ids"))
    _add(session_state.get("improv_ai_metric_ids"))
    _add(session_state.get("analysis_ai_metric_ids"))
    _add(session_state.get("analysis_mission_ids"))

    if include_creative and session_state.get("analysis_sync_creative_mission", True):
        legacy = str(session_state.get("improv_active_mission") or "")
        for mid in mission_ids_from_legacy(legacy):
            if mid not in ids:
                ids.append(mid)
    if session_state.get("analysis_custom_goal_enabled") and str(
        session_state.get("analysis_custom_goal") or ""
    ).strip():
        if "custom" not in ids:
            ids.append("custom")
    return ids[:18]


def _pc_from_hz(hz: float) -> str | None:
    if librosa is None or hz <= 0 or np.isnan(hz):
        return None
    try:
        note = str(librosa.hz_to_note(float(hz)))
        root, _ = split_chord(note.replace("♯", "#").replace("♭", "b"))
        if len(root) >= 2 and root[1] == "b":
            root = root[:2]
        return normalize_root(root)
    except Exception:
        return None


def _major_scale_pcs(key: str) -> set[str]:
    root = normalize_root(split_chord(str(key).replace("m", ""))[0])
    if root not in CHROMATIC:
        root = "C"
    idx = CHROMATIC.index(root)
    pattern = (0, 2, 4, 5, 7, 9, 11)
    return {CHROMATIC[(idx + s) % 12] for s in pattern}


def _minor_scale_pcs(key: str) -> set[str]:
    root = normalize_root(split_chord(str(key).replace("m", ""))[0])
    if root not in CHROMATIC:
        root = "A"
    idx = CHROMATIC.index(root)
    pattern = (0, 2, 3, 5, 7, 8, 10)
    return {CHROMATIC[(idx + s) % 12] for s in pattern}


def _pentatonic_pcs(key: str) -> set[str]:
    root = normalize_root(split_chord(str(key).replace("m", ""))[0])
    if root not in CHROMATIC:
        root = "C"
    idx = CHROMATIC.index(root)
    pattern = (0, 2, 4, 7, 9)
    return {CHROMATIC[(idx + s) % 12] for s in pattern}


def _guide_tone_pcs(chords: list[str]) -> set[str]:
    pcs: set[str] = set()
    for ch in chords:
        tones = chord_tone_names(ch)
        if len(tones) >= 2:
            pcs.add(normalize_root(tones[1]))
        if len(tones) >= 4:
            pcs.add(normalize_root(tones[3]))
    return pcs


def _chord_tone_pool(chords: list[str]) -> set[str]:
    pool: set[str] = set()
    for ch in chords:
        for t in chord_tone_names(ch):
            pool.add(normalize_root(t))
    return pool


def _style_profile(ctx: dict[str, Any]) -> str:
    text = " ".join(
        str(ctx.get(k) or "")
        for k in ("genre", "song", "style_label", "focus")
    ).lower()
    if any(k in text for k in ("jazz", "bossa", "bebop", "swing", "blue bossa")):
        return "jazz"
    if any(k in text for k in ("pop", "ballad", "folk", "acoustic", "perfect")):
        return "ballad"
    return "general"


def extract_improv_metrics(
    y: np.ndarray,
    sr: int,
    features: Any,
    ctx: dict[str, Any],
) -> dict[str, float]:
    """Derive 0–100 musical metrics from audio + chart context."""
    metrics: dict[str, float] = {k: 55.0 for k in (
        "melodic_diversity", "rhythmic_diversity", "motif_consistency", "motif_transformation",
        "chord_tone_accuracy", "guide_tone_usage", "scale_adherence", "pentatonic_adherence",
        "tension_release_balance", "phrase_pacing", "dynamic_contrast", "groove_consistency",
        "timing_stability", "phrase_contour_variety", "landing_note_quality", "repetition_variation",
        "resolution_strength", "rhythmic_syncopation", "space_rests", "voice_leading_smoothness",
        "chromatic_motion", "musical_expression", "articulation", "instrument_tone",
    )}

    if librosa is None:
        return metrics

    onset_times = np.asarray(getattr(features, "onset_times", []), dtype=float)
    beat_times = np.asarray(getattr(features, "beat_times", []), dtype=float)
    duration = float(getattr(features, "duration", 0) or len(y) / max(sr, 1))

    try:
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
        )
    except Exception:
        f0 = np.array([])
        voiced_flag = np.array([])

    pitch_pcs: list[str] = []
    pitch_midi: list[int] = []
    for hz, vf in zip(f0, voiced_flag):
        if not vf or hz is None or np.isnan(hz):
            continue
        pc = _pc_from_hz(float(hz))
        if pc:
            pitch_pcs.append(pc)
            try:
                pitch_midi.append(int(round(librosa.hz_to_midi(float(hz)))))
            except Exception:
                pass

    key = str(ctx.get("display_key") or "C")
    is_minor = str(key).endswith("m") or "minor" in str(key).lower()
    scale_pcs = _minor_scale_pcs(key) if is_minor else _major_scale_pcs(key)
    pent_pcs = _pentatonic_pcs(key)
    # Chord / guide-tone pools only when Upload-selected song provides real harmony
    # (key and/or chords). Named Verse/Chorus form is NOT required.
    try:
        from analysis_coach_quality import has_song_harmony_context

        song_harmony = has_song_harmony_context(ctx)
    except Exception:
        song_harmony = bool(ctx.get("target_chords") or ctx.get("display_key") or ctx.get("sections"))
    chords: list[str] = []
    if song_harmony:
        chords = list(ctx.get("target_chords") or [])
        if not chords:
            for sec_chords in (ctx.get("sections") or {}).values():
                chords.extend(sec_chords or [])
        chords = [str(c) for c in chords if c][:24]
    chord_pool = _chord_tone_pool(chords) if chords else set()
    guide_pool = _guide_tone_pcs(chords) if chords else set()
    # Scale adherence uses selected-song key when present; otherwise observed-only.

    if pitch_pcs:
        unique_ratio = len(set(pitch_pcs)) / max(len(pitch_pcs), 1)
        metrics["melodic_diversity"] = _clamp(35 + unique_ratio * 65)

        scale_hits = sum(1 for p in pitch_pcs if p in scale_pcs) / len(pitch_pcs)
        metrics["scale_adherence"] = _clamp(scale_hits * 100)

        pent_hits = sum(1 for p in pitch_pcs if p in pent_pcs) / len(pitch_pcs)
        metrics["pentatonic_adherence"] = _clamp(pent_hits * 100)

        if chord_pool:
            ct_hits = sum(1 for p in pitch_pcs if p in chord_pool) / len(pitch_pcs)
            metrics["chord_tone_accuracy"] = _clamp(ct_hits * 100)

        if guide_pool:
            gt_hits = sum(1 for p in pitch_pcs if p in guide_pool) / len(pitch_pcs)
            metrics["guide_tone_usage"] = _clamp(gt_hits * 100)
        elif not song_harmony:
            # No song harmony — do not invent chord-tone scores from a parent scale.
            metrics.pop("chord_tone_accuracy", None)
            metrics.pop("guide_tone_usage", None)

        chromatic = sum(
            1 for i in range(1, len(pitch_midi)) if abs(pitch_midi[i] - pitch_midi[i - 1]) in (1, 6)
        )
        if len(pitch_midi) > 2:
            metrics["chromatic_motion"] = _clamp(chromatic / len(pitch_midi) * 220)

        intervals = [pitch_midi[i + 1] - pitch_midi[i] for i in range(len(pitch_midi) - 1)]
        if len(intervals) >= 3:
            tri = [tuple(intervals[i : i + 3]) for i in range(len(intervals) - 2)]
            counts = Counter(tri)
            top_share = counts.most_common(1)[0][1] / len(tri) if tri else 0
            metrics["motif_consistency"] = _clamp(top_share * 100)
            unique_tri = len(set(tri)) / max(len(tri), 1)
            metrics["motif_transformation"] = _clamp(unique_tri * 85)
            metrics["repetition_variation"] = _clamp(50 + unique_tri * 45)

        direction_changes = sum(
            1
            for i in range(2, len(pitch_midi))
            if (pitch_midi[i] - pitch_midi[i - 1]) * (pitch_midi[i - 1] - pitch_midi[i - 2]) < 0
        )
        if len(pitch_midi) > 3:
            metrics["phrase_contour_variety"] = _clamp(40 + direction_changes / len(pitch_midi) * 120)

        if len(pitch_midi) > 4:
            steps = [abs(pitch_midi[i] - pitch_midi[i - 1]) for i in range(1, len(pitch_midi))]
            smooth = sum(1 for s in steps if s <= 2) / len(steps)
            metrics["voice_leading_smoothness"] = _clamp(smooth * 100)

    if len(onset_times) > 3:
        iois = np.diff(onset_times)
        cv = float(np.std(iois) / max(np.mean(iois), 1e-6))
        metrics["rhythmic_diversity"] = _clamp(40 + min(55, cv * 90))
        metrics["phrase_pacing"] = _clamp(50 + min(45, len(onset_times) / max(duration, 1) * 8))

    if len(beat_times) > 2 and len(onset_times) > 2:
        near = sum(1 for ot in onset_times if np.min(np.abs(beat_times - ot)) < 0.08)
        offbeat = len(onset_times) - near
        metrics["rhythmic_syncopation"] = _clamp(offbeat / max(len(onset_times), 1) * 100)
        metrics["landing_note_quality"] = _clamp(near / max(len(onset_times), 1) * 100)
        metrics["groove_consistency"] = _clamp(float(getattr(features, "groove_tightness", 0.5)) * 100)
        metrics["timing_stability"] = _clamp(88 - min(50, float(getattr(features, "beat_interval_cv", 0)) * 140))

    metrics["dynamic_contrast"] = _clamp(float(getattr(features, "dyn_range", 0)) * 500)
    metrics["musical_expression"] = _clamp(
        metrics["dynamic_contrast"] * 0.4 + metrics["melodic_diversity"] * 0.35 + metrics["phrase_contour_variety"] * 0.25
    )
    metrics["articulation"] = _clamp(
        float(getattr(features, "onset_strength_mean", 0) or 0) * 12
        + (1.0 - min(1.0, float(getattr(features, "zcr_mean", 0) or 0) * 8)) * 35
        + metrics["rhythmic_diversity"] * 0.25
    )
    metrics["instrument_tone"] = _clamp(
        float(getattr(features, "voiced_ratio", 0) or 0) * 55
        + min(40, float(getattr(features, "spectral_centroid_mean", 0) or 0) / 80)
    )

    rms = getattr(features, "rms", None)
    if rms is not None and len(rms) > 8:
        rms_n = (rms - np.min(rms)) / max(float(np.ptp(rms)), 1e-9)
        quiet_ratio = float(np.mean(rms_n < 0.12))
        metrics["space_rests"] = _clamp(quiet_ratio * 130)

    cents_std = getattr(features, "pitch_cents_std", None)
    if cents_std is not None:
        tension = min(100, float(cents_std) * 1.1)
        metrics["tension_release_balance"] = _clamp(55 + (tension - 50) * 0.35)
        metrics["resolution_strength"] = _clamp(100 - min(45, float(cents_std) * 0.5))

    style = _style_profile(ctx)
    if style == "jazz":
        metrics["scale_adherence"] = _clamp(metrics["scale_adherence"] * 0.92 + 8)
        metrics["tension_release_balance"] = _clamp(metrics["tension_release_balance"] + 6)
    elif style == "ballad":
        metrics["space_rests"] = _clamp(metrics["space_rests"] + 5)
        metrics["dynamic_contrast"] = _clamp(metrics["dynamic_contrast"] * 0.95)

    meter = str(ctx.get("time_signature") or "")
    if "6/8" in meter:
        metrics["rhythmic_syncopation"] = _clamp(metrics["rhythmic_syncopation"] * 0.9 + 5)

    return metrics


def _clamp(v: float, lo: float = 12.0, hi: float = 96.0) -> float:
    return float(max(lo, min(hi, v)))


def _score_from_weights(weights: dict[str, float], metrics: dict[str, float]) -> int:
    present = {k: float(metrics[k]) for k in weights if k in metrics}
    if not present:
        # No defensible primary signal — return neutral qualitative placeholder.
        return 0
    # Renormalize over available metrics only (do not invent 55 defaults).
    wsum = sum(weights[k] for k in present) or 1.0
    total = sum(present[k] * (weights[k] / wsum) for k in present)
    return int(round(_clamp(total)))


def _mission_feedback(
    mission: MissionGoal,
    score: int,
    metrics: dict[str, float],
    ctx: dict[str, Any],
    *,
    custom_text: str = "",
) -> tuple[str, str]:
    """Return (summary line, why explanation)."""
    inst = str(ctx.get("instrument") or "your instrument")
    song = str(ctx.get("song") or "this song")
    style = _style_profile(ctx)

    if mission.id == "one_motif":
        if score >= 75:
            return (
                "You repeated and evolved one melodic idea consistently through the take.",
                f"Motif consistency ({metrics.get('motif_consistency', 0):.0f}/100) shows a recognizable cell; "
                f"transformation ({metrics.get('motif_transformation', 0):.0f}/100) shows you reshaped it rhythmically.",
            )
        return (
            "The take wanders between several unrelated shapes — tighten to one 3–5 note cell.",
            "Reuse the same interval pattern at least twice before changing rhythm or register.",
        )

    if mission.id == "rhythmic_diversity":
        if score >= 72:
            return (
                "Good use of mixed note lengths and syncopated placement.",
                f"Rhythmic diversity ({metrics.get('rhythmic_diversity', 0):.0f}/100) and syncopation "
                f"({metrics.get('rhythmic_syncopation', 0):.0f}/100) show varied lengths.",
            )
        return (
            "Many phrases use similar rhythmic lengths — vary eighths, quarters, and rests.",
            "Try one bar of even eighths, then one bar with a longer note on beat 1.",
        )

    if mission.id == "motif_development":
        if score >= 70:
            return (
                "You reused a short idea and changed it rhythmically across the take.",
                f"Motif consistency ({metrics.get('motif_consistency', 0):.0f}/100) and transformation "
                f"({metrics.get('motif_transformation', 0):.0f}/100) show real development.",
            )
        return (
            "Ideas change completely each phrase — keep one 3–5 note cell and reshape it.",
            "State the motif, answer it in a new rhythm, then return to the same pitches.",
        )

    if mission.id == "phrase_structure":
        pacing = float(metrics.get("phrase_pacing", 0) or 0)
        contour = float(metrics.get("phrase_contour_variety", 0) or 0)
        space = float(metrics.get("space_rests", 0) or 0)
        if score >= 72:
            return (
                "Phrases have clear beginnings and endings with breathing room between ideas.",
                f"Phrase pacing ({pacing:.0f}/100) supports a question–answer shape.",
            )
        # Strong pacing with weaker contour/space: keep positive evidence separate from growth.
        if pacing >= 70 and (contour < 55 or space < 55):
            return (
                f"Phrase pacing was strong at approximately {pacing:.0f}/100; "
                "the main opportunity is creating more contour contrast and intentional space.",
                f"Contour variety ≈ {contour:.0f}/100 and intentional space/rests ≈ {space:.0f}/100 — "
                "plan 2-bar questions and 2-bar answers with a beat of rest between ideas.",
            )
        return (
            "Lines run together — plan 2-bar questions and 2-bar answers.",
            "Leave a beat of space before starting the next phrase.",
        )

    if mission.id == "melodic_diversity_goal":
        if score >= 72:
            return (
                "You used a healthy range of pitches without losing the thread of the solo.",
                f"Melodic variety ({metrics.get('melodic_diversity', 0):.0f}/100) stays musical, not random.",
            )
        return (
            "The melody stays in a narrow band — explore one octave higher or lower on the next take.",
            "Keep stable tones on downbeats while using passing tones between them.",
        )

    if mission.id == "scale_connection":
        # Interpret from scale/mode evidence magnitude — not melodic diversity /
        # phrase-contour variety (those belong to other criteria).
        adherence = float(metrics.get("scale_adherence", 0) or 0)
        chord_tone = metrics.get("chord_tone_accuracy")
        guide_tone = metrics.get("guide_tone_usage")
        support_bits: list[str] = []
        if chord_tone is not None:
            support_bits.append(f"chord-tone fit {float(chord_tone):.0f}/100")
        if guide_tone is not None:
            support_bits.append(
                f"guide-tone usage {float(guide_tone):.0f}/100 "
                "(3rds; 7ths only where encoded)"
            )
        support = ("; " + "; ".join(support_bits)) if support_bits else ""
        song = str(ctx.get("song") or ctx.get("song_source_name") or "the selected song").strip()
        key = str(ctx.get("display_key") or "").strip()
        key_bit = f" in {key}" if key else ""
        if adherence >= 85:
            return (
                f"Scale adherence was strong at about {adherence:.0f}/100{key_bit}, "
                "with only a small number of notes outside the selected tonal material.",
                f"Primary evidence is scale/key membership vs {song}{support}.",
            )
        if adherence >= 70:
            return (
                f"Scale adherence was solid at about {adherence:.0f}/100{key_bit}, "
                "with some notes outside the selected tonal material to clean up.",
                f"Primary evidence is scale/key membership vs {song}{support}.",
            )
        return (
            f"Scale adherence is about {adherence:.0f}/100{key_bit} — "
            "a meaningful share of notes sat outside the selected key/mode.",
            f"Constrain the next pass to {key or 'the song'} scale tones against "
            f"{song}'s chords; resolve non-chord tones into chord tones.",
        )

    if mission.id == "deep_harmony":
        if score >= 75:
            return (
                "You outlined the harmony clearly — chord tones and guide tones show up on strong beats.",
                f"Chord-tone accuracy ({metrics.get('chord_tone_accuracy', 0):.0f}/100) tracks the chart.",
            )
        return (
            "Harmony is implied but fuzzy — sing the root of each chord before improvising.",
            "Target chord tones that each symbol encodes at phrase endings "
            "(3rds always; 7ths only when the chord includes them).",
        )

    if mission.id == "timing_groove":
        from analysis_coach_quality import (
            meter_aware_groove_click_tip,
            resolve_analysis_meter,
            instrument_family,
        )

        if score >= 75:
            return (
                "Your time feels steady and grooves with the pulse.",
                f"Groove ({metrics.get('groove_consistency', 0):.0f}/100) and timing ({metrics.get('timing_stability', 0):.0f}/100) are solid.",
            )
        tip = meter_aware_groove_click_tip(
            resolve_analysis_meter(ctx),
            family=instrument_family(str(ctx.get("instrument") or "")),
        )
        return (
            f"Rhythm wavers against the beat — {tip}",
            "Clap the groove, then play only long tones in time before restoring the phrase.",
        )

    if mission.id == "articulation":
        if score >= 72:
            return (
                "Attacks and note lengths are varied — the line has shape.",
                f"Articulation score ({metrics.get('articulation', 0):.0f}/100) shows intentional attacks.",
            )
        return (
            "Every note has the same attack — try softer starts and clearer accents on phrase peaks.",
            "Shape the phrase: lighter on approach notes, clearer accents on destination notes.",
        )

    if mission.id == "instrument_tone":
        if score >= 72:
            return (
                "Tone stays consistent and supports the mood of the take.",
                f"Tone steadiness ({metrics.get('instrument_tone', 0):.0f}/100) reads well on this recording.",
            )
        return (
            "Tone thins or wavers — warm up long tones before recording the take.",
            "Aim for one consistent tone color per phrase, not note-to-note surprises.",
        )

    if mission.id == "mission_completion":
        if score >= 75:
            return (
                "Your take aligns well with what you set out to practice in Creative Lab.",
                "Keep using the same mission focus for the next upload to track progress.",
            )
        return (
            "The recording does not yet match your stated practice mission — narrow the focus.",
            "Re-record one section only, with the mission checklist in front of you.",
        )

    if mission.id == "chord_tone_targeting":
        if score >= 78:
            return (
                "You often landed on stable notes during chord changes.",
                f"Chord-tone accuracy ({metrics.get('chord_tone_accuracy', 0):.0f}/100) and landing quality "
                f"({metrics.get('landing_note_quality', 0):.0f}/100) align with the chart.",
            )
        return (
            "Pitch choices often float outside the harmony — aim at roots/3rds/5ths on downbeats.",
            f"Over {song}, sing each chord root before improvising on {inst}.",
        )

    if mission.id == "tension_release":
        if score >= 68:
            return (
                "You created tension that resolved across phrase boundaries.",
                f"Tension/release balance ({metrics.get('tension_release_balance', 0):.0f}/100) shows contrast.",
            )
        return (
            "You created some tension, but your phrases often resolved too quickly.",
            "Hold one color tone through beat 4, then land on a chord tone on beat 1.",
        )

    if mission.id == "space_silence":
        if score >= 70:
            return (
                "Rests and low-energy gaps give the line room to breathe.",
                f"Space/rest score ({metrics.get('space_rests', 0):.0f}/100) shows intentional gaps.",
            )
        return (
            "The line is dense — add rests every 2 bars as in your mission brief.",
            "Mute for one beat after each 2-bar question phrase.",
        )

    if mission.id == "guide_tones":
        if score >= 75:
            return (
                "Guide tones (3rds; 7ths only when encoded) show up as clear phrase destinations.",
                f"Guide-tone usage ({metrics.get('guide_tone_usage', 0):.0f}/100) tracks the progression.",
            )
        return (
            "Land on guide tones at phrase endings — 3rds for triads, 3rds+7ths when the "
            "chord symbol includes a 7th.",
            "End each 2-bar phrase on the current chord’s 3rd (and 7th only if present).",
        )

    if mission.id == "custom" and custom_text:
        return (
            f"Custom goal “{custom_text[:80]}” — overall musical expression scored {score}%.",
            "This score blends phrasing, dynamics, and groove from your recording.",
        )

    if style == "jazz":
        return (
            f"Jazz-oriented read for {mission.label} on {song}.",
            f"Syncopation ({metrics.get('rhythmic_syncopation', 0):.0f}/100) and contour "
            f"({metrics.get('phrase_contour_variety', 0):.0f}/100) shaped this score.",
        )

    if score >= 72:
        return (
            f"Solid work on {mission.label} for {song}.",
            f"Key drivers: {', '.join(f'{k.replace('_', ' ')} {metrics.get(k, 0):.0f}' for k in list(mission.weights)[:3])}.",
        )
    return (
        f"Room to grow on {mission.label} — loop one section slowly.",
        f"Focus metric: {max(mission.weights, key=lambda k: mission.weights[k]).replace('_', ' ')}.",
    )


def _looks_like_praise(text: str) -> bool:
    t = str(text or "").strip().lower()
    if not t:
        return False
    negative = (
        "try ",
        "every note has the same",
        "wavers",
        "wanders",
        "fuzzy",
        "narrow",
        "thins",
        "dense —",
        "room to grow",
        "does not yet",
        "float outside",
        "tighten",
        "leave a beat",
        "aim at",
        "add rests",
        "land on",
        "hold one color",
        "mute for",
        "re-record",
        "narrow the focus",
    )
    if any(n in t for n in negative):
        return False
    positive = (
        "solid",
        "good ",
        "clear",
        "strong",
        "varied",
        "consistent",
        "healthy",
        "aligns",
        "are solid",
        "well with",
        "recognizable",
        "real development",
        "breathing room",
        "tracks the chart",
        "tracks the progression",
        "shows intentional",
        "reads well",
    )
    return any(p in t for p in positive)


def _coach_result_fields(score: int, summary: str, why: str) -> tuple[str, str]:
    """Split feedback into evidence-based praise vs actionable improvement."""
    summary = str(summary or "").strip()
    why = str(why or "").strip()
    summary_praise = _looks_like_praise(summary)
    why_praise = _looks_like_praise(why)

    if score >= 78:
        went_well = summary if summary else why
        if why and not why_praise and why != summary:
            improve_to = why
        else:
            improve_to = (
                "Push this strength into a slightly harder context "
                "(faster tempo, longer form, or denser phrase)."
            )
        return went_well, improve_to

    if score >= 62:
        if summary_praise:
            went_well = summary
            if why and not why_praise:
                improve_to = why
            else:
                improve_to = (
                    "Keep refining consistency so the strong moments become the default."
                )
        else:
            went_well = (
                "There are usable moments in this take — keep the intentional shapes you already found."
            )
            improve_to = summary or why or "Loop one section slowly and record again."
            if why and why != summary and not why_praise:
                improve_to = f"{improve_to} {why}".strip()
        return went_well, improve_to

    # Even at lower overall scores, keep real positive evidence in went_well when present
    # (e.g. strong phrase pacing with weak contour/space).
    if summary_praise:
        went_well = summary
        improve_to = (
            why
            if why and not why_praise
            else "Loop one section at a slower tempo and record again."
        )
        return went_well, improve_to

    went_well = "Your take gives a clear starting point — keep ideas shorter and more focused."
    if summary:
        improve_to = summary
        if why and not why_praise and why != summary:
            improve_to = f"{summary} {why}".strip()
    else:
        improve_to = why or "Loop one section at a slower tempo and record again."
    return went_well, improve_to


def _blend_performance_metrics(
    metrics: dict[str, float],
    performance_scores: dict[str, int] | None,
) -> dict[str, float]:
    if not performance_scores:
        return metrics
    out = dict(metrics)
    timing = float(performance_scores.get("timing", 70))
    groove = float(performance_scores.get("groove", 70))
    tone = float(performance_scores.get("tone", 70))
    technique = float(performance_scores.get("technique", 70))
    out["timing_stability"] = _clamp(out["timing_stability"] * 0.5 + timing * 0.5)
    out["groove_consistency"] = _clamp(out["groove_consistency"] * 0.5 + groove * 0.5)
    out["instrument_tone"] = _clamp(out["instrument_tone"] * 0.45 + tone * 0.55)
    out["articulation"] = _clamp(out["articulation"] * 0.5 + technique * 0.5)
    return out


def _instrument_mission_tips(instrument: str, mission_id: str, score: int) -> list[str]:
    """Criterion-specific tips only. Shared breath/tempo advice is attached once later."""
    from analysis_coach_quality import has_song_form_context, instrument_family

    fam = instrument_family(instrument)
    tips: list[str] = []
    if fam == "guitar":
        if mission_id in ("chord_tone_targeting", "guide_tones", "deep_harmony"):
            tips.append("Arpeggiate chord shapes in one position; land on the top voice for phrase endings.")
        if mission_id in ("one_motif", "motif_development"):
            tips.append("Keep the motif on adjacent strings so you can vary rhythm without jumping positions.")
        if mission_id in ("phrase_structure", "phrasing"):
            tips.append("Listen for fret-hand shifts — smooth position changes support clean phrase endings.")
    elif fam == "piano":
        if mission_id in ("voice_leading", "chord_tone_targeting", "deep_harmony"):
            tips.append("LH shell voicings + RH chord tones on beats 1 and 3 clarify harmony.")
        if mission_id == "dynamic_contrast":
            tips.append("Practice one chorus at mp, one at mf — keep time identical.")
    elif fam == "flute":
        if mission_id in ("phrase_structure", "phrasing"):
            tips.append("Think question–answer: 2 bars in, 1 beat rest, 2 bars out — keep the air stream steady.")
        if mission_id == "articulation":
            tips.append("Alternate tongued vs legato on the same scale pattern — match air, change only the tongue.")
        if mission_id in ("instrument_tone", "timing_groove"):
            tips.append("Long tones with a drone — stabilize embouchure before adding phrase shape.")
    elif fam in ("saxophone", "clarinet", "trumpet", "trombone"):
        if mission_id in ("phrase_structure", "phrasing"):
            tips.append("Think question–answer: 2 bars in, 1 beat rest, 2 bars out.")
        if mission_id == "articulation":
            tips.append("Practice one pitch with soft–accent–soft attacks while air stays constant.")
    elif fam == "voice":
        if mission_id in ("phrase_structure", "phrasing"):
            tips.append("Mark breath spots every 2 bars before singing the take again.")
    if mission_id == "scale_connection":
        tips = [
            "Play the Concert Key scale against the song's actual chord progression; "
            "land chord tones that each symbol encodes on strong beats.",
            "Loop one section and constrain note choices to the relevant scale/mode, "
            "resolving approach tones into stable chord tones.",
        ]
    # Song-form-gated tip only when harmony exists.
    # (Caller may pass ctx via score_missions — keep mission-local here.)
    _ = score  # reserved for future severity gating
    return tips[:3]



def _criterion_observed_evidence(
    mission: MissionGoal,
    metrics: dict[str, float],
    ctx: dict[str, Any],
) -> tuple[list[str], bool]:
    """Build evidence lines for a selected Evaluating Criterion.

    Returns (evidence_lines, has_defensible_primary_metric).
    """
    lines: list[str] = []
    primary_keys = [k for k, w in sorted(mission.weights.items(), key=lambda kv: -kv[1])[:3]]
    present = [k for k in primary_keys if k in metrics]
    limited = len(present) == 0
    for k in present:
        lines.append(f"{k.replace('_', ' ')} ≈ {float(metrics[k]):.0f}/100")
    if mission.id in {"scale_connection", "chord_tone_targeting", "guide_tones", "deep_harmony"}:
        song = str(ctx.get("song") or ctx.get("song_source_name") or "").strip()
        key = str(ctx.get("display_key") or "").strip()
        if song or key:
            lines.append(
                "Harmonic frame: "
                + (song if song else "selected song")
                + (f" / {key}" if key else "")
            )
        rtype = str(ctx.get("recording_type") or "").strip().lower().replace("_", " ")
        if "backing" in rtype or ctx.get("backing_track_context"):
            lines.append(
                "Mixed-recording caution: pitch-class evidence may include backing content."
            )
    if mission.id in {"dynamic_contrast"}:
        if "dynamic_contrast" in metrics:
            lines.append(f"Dynamic contrast signal ≈ {float(metrics['dynamic_contrast']):.0f}/100")
    if mission.id in {"articulation"}:
        if "articulation" in metrics:
            lines.append(f"Articulation signal ≈ {float(metrics['articulation']):.0f}/100")
    if mission.id in {"instrument_tone"}:
        if "instrument_tone" in metrics:
            lines.append(f"Tone signal ≈ {float(metrics['instrument_tone']):.0f}/100")
    if limited:
        lines.append(
            "Limited direct metric coverage for this criterion on this take — "
            "coaching stays qualitative rather than inventing a borrowed score."
        )
    return lines, not limited


def score_missions(
    mission_ids: list[str],
    metrics: dict[str, float],
    ctx: dict[str, Any],
    *,
    custom_goal: str = "",
) -> list[dict[str, Any]]:
    from analysis_coach_quality import dedupe_recommendations, has_song_form_context, has_song_harmony_context, instrument_family

    results: list[dict[str, Any]] = []
    shared_tips: list[str] = []
    fam = instrument_family(str(ctx.get("instrument") or ""))
    song_form = has_song_form_context(ctx)
    song_harmony = has_song_harmony_context(ctx)

    for mid in mission_ids:
        goal = MISSION_BY_ID.get(mid)
        if not goal:
            continue
        score = _score_from_weights(goal.weights, metrics)
        if goal.id == "mission_completion" and ctx.get("active_practice_mission_ids"):
            sub = [
                _score_from_weights(MISSION_BY_ID[mid].weights, metrics)
                for mid in ctx["active_practice_mission_ids"]
                if mid in MISSION_BY_ID
            ]
            if sub:
                score = int(round(sum(sub) / len(sub)))
        summary, why = _mission_feedback(goal, score, metrics, ctx, custom_text=custom_goal)
        # Gate song-section wording in generic feedback when no form exists.
        if not song_form:
            for bad in ("verse", "chorus", "backing"):
                if bad in summary.lower():
                    summary = summary.replace("Verse", "phrase").replace("verse", "phrase")
                    summary = summary.replace("Chorus", "peak phrase").replace("chorus", "peak phrase")
                if bad in why.lower():
                    why = why.replace("Verse", "phrase").replace("verse", "phrase")
                    why = why.replace("Chorus", "peak phrase").replace("chorus", "peak phrase")
                    why = why.replace("Mirror the backing:", "Shape the phrase:")
        went_well, improve_to = _coach_result_fields(score, summary, why)
        tips = _instrument_mission_tips(str(ctx.get("instrument") or ""), goal.id, score)
        evidence_lines, has_primary = _criterion_observed_evidence(goal, metrics, ctx)
        assessment = (
            f"{score}/100"
            if has_primary and score > 0
            else "Limited evidence / qualitative assessment"
        )
        drill = ""
        if tips:
            drill = str(tips[0])
        if goal.id == "scale_connection" and not drill:
            key = str(ctx.get("display_key") or "the song").strip() or "the song"
            song = str(ctx.get("song") or "the selected song").strip() or "the selected song"
            drill = (
                f"Play the {key} scale against {song}'s chord progression; "
                "resolve approach tones into chord tones that each symbol encodes."
            )
        results.append(
            {
                "id": goal.id,
                "label": goal.label,
                "score": score if has_primary else None,
                "assessment": assessment,
                "summary": summary,
                "why": why,
                "observed_evidence": evidence_lines,
                "went_well": went_well,
                "improve_to": improve_to,
                "drill": drill,
                "tips": tips,
                "limited_evidence": not has_primary,
            }
        )
        # Breath/tempo logistics must not attach to scale/mode or other harmonic criteria.
        _harmonic_ids = {
            "scale_connection",
            "chord_tone_targeting",
            "guide_tones",
            "deep_harmony",
            "voice_leading",
            "pentatonic_focus",
        }
        try:
            score_i = int(score) if score is not None else 0
        except (TypeError, ValueError):
            score_i = 0
        if score_i < 65 and goal.id not in _harmonic_ids:
            if fam == "flute":
                shared_tips.append("Record one pass focusing on breath — longer notes need supported air.")
            elif fam in ("saxophone", "clarinet", "trumpet", "trombone"):
                shared_tips.append("Record one pass focusing on breath — longer notes need supported air.")
            if song_harmony:
                shared_tips.append("Slow the backing track 10–15 BPM and record two takes back-to-back.")
            else:
                shared_tips.append("Slow the metronome 10–15 BPM and record two takes back-to-back.")

    shared_tips = dedupe_recommendations(shared_tips, limit=2)
    if shared_tips and results:
        _harmonic_ids = {
            "scale_connection",
            "chord_tone_targeting",
            "guide_tones",
            "deep_harmony",
            "voice_leading",
            "pentatonic_focus",
        }
        candidates = [r for r in results if r.get("id") not in _harmonic_ids]
        if not candidates:
            candidates = []
        if candidates:
            weakest = min(
                candidates,
                key=lambda r: int(r.get("score") or 0) if r.get("score") is not None else 0,
            )
            weakest["tips"] = dedupe_recommendations(list(weakest.get("tips") or []) + shared_tips, limit=4)
            if not weakest.get("drill") and weakest.get("tips"):
                weakest["drill"] = str(weakest["tips"][0])
    return results


def build_mission_recommendation(
    mission_results: list[dict[str, Any]],
    ctx: dict[str, Any],
    metrics: dict[str, float],
) -> str:
    from analysis_coach_quality import has_song_form_context

    if not mission_results:
        return "Select Evaluating Criteria above, then upload a take for criterion-specific feedback."
    weakest = min(
        mission_results,
        key=lambda x: int(x["score"]) if x.get("score") is not None else 0,
    )
    bpm = int(ctx.get("practice_bpm") or 70)
    section_hint = ""
    if has_song_form_context(ctx):
        for sec in (ctx.get("sections") or {}):
            if "verse" in sec.lower():
                section_hint = f" over only the **{sec}** section"
                break
    action = str(weakest.get("improve_to") or weakest.get("summary") or "").strip()
    return (
        f"Next practice: work on {weakest['label']}{section_hint} "
        f"at {max(55, bpm - 12)} BPM on {ctx.get('instrument', 'your instrument')}. "
        f"{action}"
    )


def analyze_improvisation_missions(
    y: np.ndarray,
    sr: int,
    features: Any,
    ctx: dict[str, Any],
    mission_ids: list[str],
    *,
    custom_goal: str = "",
    performance_scores: dict[str, int] | None = None,
) -> dict[str, Any]:
    empty = {
        "mission_results": [],
        "musical_metrics": {},
        "mission_coach_summary": "",
        "mission_strongest": "",
        "mission_weakest": "",
        "mission_next_recommendation": "",
        "overall_improv_score": 0,
    }
    if not mission_ids:
        return empty

    metrics = extract_improv_metrics(y, sr, features, ctx)
    metrics = _blend_performance_metrics(metrics, performance_scores)
    results = score_missions(mission_ids, metrics, ctx, custom_goal=custom_goal)
    if not results:
        return {**empty, "musical_metrics": metrics}

    ranked = sorted(
        results,
        key=lambda x: int(x["score"]) if x.get("score") is not None else 0,
    )
    weakest = ranked[0]
    strongest = ranked[-1]
    scored = [r for r in results if r.get("score") is not None]
    avg = (sum(int(r["score"]) for r in scored) / len(scored)) if scored else 0
    overall = int(round(avg))

    mission_eval = bool(ctx.get("mission_evaluation_active"))
    if mission_eval:
        overall_line = f"Overall improvisation score: **{overall}%**."
    else:
        overall_line = f"Overall selected-criteria assessment: **{overall}%**."
    base = (
        f"Evaluated {len(results)} criteria against **{ctx.get('song') or 'your take'}** "
        f"({ctx.get('display_key') or ''}, {ctx.get('instrument') or ''}). "
        f"{overall_line}"
    )
    # Strongest/Weakest ranking only makes sense with 2+ criteria.
    if len(results) >= 2:
        summary = (
            f"{base} "
            f"Strongest: **{strongest['label']}** ({strongest['score']}%). "
            f"Grow next: **{weakest['label']}** ({weakest['score']}%)."
        )
        strongest_line = f"{strongest['label']} — {strongest['score']}%"
        weakest_line = f"{weakest['label']} — {weakest['score']}%"
    else:
        only = results[0]
        only_score = only.get("score")
        score_bit = f"{only_score}%" if only_score is not None else "qualitative"
        summary = f"{base} **{only['label']}**: {score_bit}."
        strongest_line = ""
        weakest_line = ""

    return {
        "mission_results": results,
        "musical_metrics": metrics,
        "mission_coach_summary": summary,
        "mission_strongest": strongest_line,
        "mission_weakest": weakest_line,
        "mission_next_recommendation": build_mission_recommendation(results, ctx, metrics),
        "overall_improv_score": overall,
        "mission_ids": mission_ids,
        "custom_goal": custom_goal,
    }


def sync_analysis_missions_from_creative(session_state: dict) -> None:
    """When navigating to Upload Analysis, copy Improvisation Intelligence metric picks."""
    improv_ids = list(session_state.get("improv_ai_metric_ids") or [])
    if improv_ids:
        session_state["analysis_ai_metric_ids"] = list(improv_ids)
        session_state["analysis_mission_ids"] = list(improv_ids)

    legacy = str(session_state.get("improv_active_mission") or "")
    mapped = mission_ids_from_legacy(legacy)
    if mapped:
        existing = list(session_state.get("analysis_ai_metric_ids") or session_state.get("analysis_mission_ids") or [])
        for mid in mapped:
            if mid not in existing:
                existing.append(mid)
        session_state["analysis_ai_metric_ids"] = existing[:18]
        session_state["analysis_mission_ids"] = existing[:18]
    session_state["analysis_sync_creative_mission"] = True


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def load_mission_history() -> list[dict[str, Any]]:
    """Mission score rows from unified AI performance history."""
    try:
        from ai_performance_history import load_performance_history

        rows: list[dict[str, Any]] = []
        for snap in load_performance_history():
            missions = snap.get("mission_results") or []
            if not missions:
                continue
            rows.append(
                {
                    "date": snap.get("date", ""),
                    "recorded_at": snap.get("recorded_at", ""),
                    "song": snap.get("song", ""),
                    "instrument": snap.get("instrument", ""),
                    "level": snap.get("level", ""),
                    "focus": snap.get("focus", ""),
                    "missions": [
                        {"id": m.get("id"), "label": m.get("label"), "score": m.get("score")}
                        for m in missions
                    ],
                    "filename": snap.get("filename", ""),
                    "musical_metrics": dict(snap.get("musical_metrics") or {}),
                }
            )
        if rows:
            return rows
    except Exception:
        pass
    if not MISSION_HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(MISSION_HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_mission_history(entries: list[dict[str, Any]]) -> None:
    MISSION_HISTORY_FILE.write_text(
        json.dumps(entries[-100:], indent=2),
        encoding="utf-8",
    )


def append_mission_history(
    result: dict[str, Any],
    ctx: dict[str, Any],
    mission_block: dict[str, Any],
) -> None:
    """Legacy hook — writes to unified AI performance history."""
    if not mission_block.get("mission_results"):
        return
    try:
        from ai_performance_history import append_performance_record, resolve_analysis_source

        merged = dict(result)
        merged.update(mission_block)
        source = str(ctx.get("analysis_source") or "")
        if not source:
            source = resolve_analysis_source(ctx if isinstance(ctx, dict) else {})
        append_performance_record(merged, ctx=ctx, source=source or "Upload Analysis")
        return
    except Exception:
        pass
    entry = {
        "date": date.today().isoformat(),
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "song": result.get("song") or ctx.get("song", ""),
        "instrument": result.get("instrument") or ctx.get("instrument", ""),
        "level": result.get("level") or ctx.get("level", ""),
        "focus": result.get("focus") or ctx.get("focus", ""),
        "mission_ids": list(mission_block.get("mission_ids") or []),
        "missions": [
            {"id": m["id"], "label": m["label"], "score": m["score"]}
            for m in mission_block.get("mission_results") or []
        ],
        "musical_metrics": dict(mission_block.get("musical_metrics") or {}),
        "filename": result.get("filename", ""),
    }
    hist = []
    if MISSION_HISTORY_FILE.exists():
        try:
            data = json.loads(MISSION_HISTORY_FILE.read_text(encoding="utf-8"))
            hist = data if isinstance(data, list) else []
        except Exception:
            hist = []
    hist.append(entry)
    save_mission_history(hist)


def mission_progress_trends(mission_id: str, limit: int = 12) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for row in load_mission_history():
        for m in row.get("missions") or []:
            if m.get("id") == mission_id:
                points.append(
                    {
                        "date": row.get("date", ""),
                        "score": int(m.get("score", 0)),
                        "song": row.get("song", ""),
                    }
                )
    return points[-limit:]
