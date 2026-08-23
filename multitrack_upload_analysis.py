"""Multitrack Upload Analysis — input contracts + orchestration (Layer vs Mix)."""

from __future__ import annotations

import re
from typing import Any

from recording_analysis_context import (
    RECORDING_TYPE_MT_LAYER,
    RECORDING_TYPE_MT_MIX,
    coerce_focus_list,
    format_focus_list,
    normalize_instrument_focuses_map,
)


def is_multitrack_layer_type(recording_type: Any) -> bool:
    text = str(recording_type or "").strip().lower().replace("_", " ")
    return "layer" in text


def is_multitrack_mix_type(recording_type: Any) -> bool:
    text = str(recording_type or "").strip().lower().replace("_", " ")
    if "layer" in text:
        return False
    # "Multitrack mix" / mix / ensemble blend
    return ("mix" in text) or text in {"multitrack", "ensemble", ""}


def resolve_multitrack_target_layer(ctx: dict[str, Any] | None) -> str:
    ctx = dict(ctx or {})
    target = str(ctx.get("target_layer") or "").strip()
    if target:
        return target
    instruments = ctx.get("instruments") or []
    if isinstance(instruments, (list, tuple)) and instruments:
        return str(instruments[0] or "").strip()
    return str(ctx.get("instrument") or "").strip()


def _feature_attr(features: Any, name: str, default: Any = None) -> Any:
    if features is None:
        return default
    if isinstance(features, dict):
        return features.get(name, default)
    return getattr(features, name, default)


def _mapped_score_for_focus(focus: str, scores: dict[str, Any] | None) -> int | None:
    """Map a Practice Focus to an existing performance score when the signal is real.

    Dynamics intentionally returns None — there is no dedicated Dynamics score in the
    baseline performance map, and Musicality must not be borrowed as a stand-in.

    Phrasing also returns None here — Phrasing uses phrase-specific musical metrics
    (pacing / contour / space), not the broader Musicality score.
    """
    scores = dict(scores or {})
    key = " ".join(str(focus or "").strip().lower().replace("/", " ").split())
    if not key:
        return None
    if "dynamic" in key:
        return None
    if "phras" in key:
        return None
    if "articulation" in key or key in {"technique", "tonguing", "attack"}:
        val = scores.get("technique")
    elif key == "tone" or "tone color" in key or "timbre" in key:
        val = scores.get("tone")
    elif "musicality" in key or "expression" in key:
        val = scores.get("musicality")
    elif "timing" in key or key == "groove" or "rhythm" in key:
        # Prefer groove when present; fall back to timing.
        val = scores.get("groove")
        if val is None:
            val = scores.get("timing")
    elif "pitch" in key or "intonation" in key:
        val = scores.get("pitch")
    else:
        return None
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _is_coaching_advice_line(text: str) -> bool:
    """True when a line is imperative coaching rather than observed evidence."""
    t = str(text or "").strip().lower()
    if not t:
        return False
    coaching_markers = (
        "keep ",
        "shape ",
        "leave ",
        "practice ",
        "try ",
        "aim ",
        "focus on",
        "make sure",
        "should ",
        "deep-dive:",
        "next take",
        "loop ",
        "mark breath",
        "not every note",
    )
    return any(m in t for m in coaching_markers)


def _phrase_metric_bundle(musical_metrics: dict[str, Any] | None) -> dict[str, float]:
    """Collect available phrase-specific metrics for Phrasing Focus scoring."""
    metrics = dict(musical_metrics or {})
    out: dict[str, float] = {}
    for key in (
        "phrase_pacing",
        "phrase_contour_variety",
        "space_rests",
        "landing_note_quality",
    ):
        if key in metrics and metrics.get(key) is not None:
            try:
                out[key] = float(metrics[key])
            except (TypeError, ValueError):
                continue
    return out


def _score_phrasing_from_metrics(phrase_metrics: dict[str, float]) -> int | None:
    """Score Phrasing from phrase evidence — never from overall Musicality.

    Weights match the broader Phrasing criterion family when all signals exist:
    pacing 0.35, contour 0.30, space/rests 0.20, landing quality 0.15.
    Missing keys are dropped and remaining weights renormalized.
    """
    if not phrase_metrics:
        return None
    weights = {
        "phrase_pacing": 0.35,
        "phrase_contour_variety": 0.30,
        "space_rests": 0.20,
        "landing_note_quality": 0.15,
    }
    present = {k: weights[k] for k in weights if k in phrase_metrics}
    if not present:
        return None
    total_w = sum(present.values()) or 1.0
    score = sum(phrase_metrics[k] * (present[k] / total_w) for k in present)
    return int(round(max(0.0, min(100.0, score))))


def _phrasing_interpretation(phrase_metrics: dict[str, float], score: int | None) -> tuple[str, str, str]:
    """Return (assessment, went_well, improve_to) for Phrasing Focus."""
    pacing = phrase_metrics.get("phrase_pacing")
    contour = phrase_metrics.get("phrase_contour_variety")
    space = phrase_metrics.get("space_rests")
    if score is None:
        return (
            "Qualitative phrasing read — limited phrase-specific metrics on this take",
            "Phrase material is present to shape more deliberately.",
            "Next take: plan clear phrase destinations and leave intentional rests between ideas.",
        )
    pacing_i = int(round(pacing)) if pacing is not None else None
    contour_i = int(round(contour)) if contour is not None else None
    space_i = int(round(space)) if space is not None else None
    strong_pace = pacing is not None and pacing >= 70
    weak_shape = (contour is not None and contour < 55) or (space is not None and space < 55)
    if score >= 75 and not weak_shape:
        assessment = f"{score}/100 (phrase pacing / contour / space)"
        went = "Phrase shape is clear overall — pacing, contour, and space support musical arcs."
        improve = "Keep refining destination notes and intentional rests so strong phrases become consistent."
    elif strong_pace and weak_shape:
        assessment = f"{score}/100 — developing phrase shape (strong pacing; weaker contour/space)"
        bits = []
        if pacing_i is not None:
            bits.append(f"pacing ≈ {pacing_i}/100")
        went = (
            "Phrase pacing is relatively strong"
            + (f" ({bits[0]})" if bits else "")
            + "; contour variety and intentional space need more contrast."
        )
        improve_bits = []
        if contour_i is not None:
            improve_bits.append(f"more contour variety (≈ {contour_i}/100)")
        if space_i is not None:
            improve_bits.append(f"more intentional space/rests (≈ {space_i}/100)")
        improve = (
            "Create "
            + (" and ".join(improve_bits) if improve_bits else "more contour contrast and breathing space")
            + " between ideas."
        )
    elif score >= 55:
        assessment = f"{score}/100 — moderate / developing phrasing"
        went = "Some phrase pacing and shape are usable — keep the clearer moments."
        improve = "Vary phrase arcs and leave intentional rests so ideas do not run together."
    else:
        assessment = f"{score}/100 — phrasing needs clearer shape and space"
        went = "There is enough phrase material to build from."
        improve = "Plan shorter ideas with clear endings and a beat of rest before the next phrase."
    return assessment, went, improve


def prune_instrument_focuses_to_project(
    instrument_focuses: Any,
    instruments: list[str] | None,
) -> dict[str, list[str]]:
    """Keep Focus maps aligned with the current Project instruments list only."""
    selected = [str(i).strip() for i in (instruments or []) if str(i).strip()]
    mapping = normalize_instrument_focuses_map(instrument_focuses)
    if not selected:
        return mapping
    return {inst: list(mapping.get(inst) or []) for inst in selected}


def _dynamics_qualitative_label(*, dyn_flatness: float, dyn_range: float) -> str:
    """Human Dynamics assessment from energy contrast — never a borrowed score."""
    # dyn_flatness ≈ 1 means little contrast; lower means more amplitude variation.
    if dyn_range <= 0 and dyn_flatness >= 0.95:
        return "Limited measurable contrast"
    if dyn_flatness < 0.35:
        return "Clear contrast"
    if dyn_flatness < 0.55:
        return "Moderate contrast"
    if dyn_flatness < 0.75:
        return "Developing contrast"
    return "Limited contrast"


def _energy_trajectory_note(features: Any) -> str:
    energy = _feature_attr(features, "energy_curve", None)
    try:
        import numpy as np

        if energy is None:
            return ""
        arr = np.asarray(energy, dtype=float).ravel()
        if arr.size < 8:
            return ""
        third = max(1, arr.size // 3)
        first = float(np.mean(arr[:third]))
        mid = float(np.mean(arr[third : 2 * third]))
        last = float(np.mean(arr[-third:]))
        peak = max(first, mid, last)
        floor = min(first, mid, last)
        if peak <= 1e-9:
            return "Energy contour stayed near the noise floor."
        rise = (last - first) / max(peak, 1e-9)
        if rise > 0.18:
            return "Energy generally increased through the take (build / crescendo tendency)."
        if rise < -0.18:
            return "Energy generally decreased through the take (release / decrescendo tendency)."
        if (mid - floor) / max(peak, 1e-9) > 0.2 and (peak - mid) / max(peak, 1e-9) > 0.12:
            return "Energy rose into phrase peaks and then settled — some intentional contour."
        return "Energy stayed relatively even across early/mid/late regions."
    except Exception:
        return ""



def _is_mixed_backing(ctx: dict[str, Any] | None) -> bool:
    ctx = dict(ctx or {})
    rtype = str(ctx.get("recording_type") or "").strip().lower().replace("_", " ")
    return "backing" in rtype or bool(ctx.get("backing_track_context"))


def _is_multitrack_mix_ctx(ctx: dict[str, Any] | None) -> bool:
    ctx = dict(ctx or {})
    rtype = str(ctx.get("recording_type") or "").strip().lower().replace("_", " ")
    mode = str(ctx.get("multitrack_mode") or "").strip().lower()
    return ("mix" in rtype) or mode.startswith("mix")


def _mix_has_isolated_stems(
    ctx: dict[str, Any] | None,
    *,
    uploaded_track_count: int | None = None,
) -> bool:
    ctx = dict(ctx or {})
    if uploaded_track_count is None:
        uploaded_track_count = int(
            ctx.get("uploaded_track_count")
            or ctx.get("comparison_stem_count")
            or 1
        )
    if int(uploaded_track_count or 1) >= 2:
        return True
    return bool(ctx.get("has_isolated_stems") or ctx.get("source_separated"))


def _mixed_backing_subject(ctx: dict[str, Any] | None, target: str = "") -> str:
    if _is_multitrack_mix_ctx(ctx) and not _mix_has_isolated_stems(ctx):
        return "The ensemble mix"
    if _is_mixed_backing(ctx):
        return "The mixed recording"
    return (str(target or "").strip() or "This take")


def _mixed_attribution_confidence(ctx: dict[str, Any] | None, *, family: str = "") -> str:
    if _is_multitrack_mix_ctx(ctx) and not _mix_has_isolated_stems(ctx):
        return (
            "Limited instrument attribution — one mixed ensemble file without isolated "
            "stems or source separation; treat per-instrument claims cautiously."
        )
    if bool(ctx and ctx.get("mix_polyphony_limited_attribution")):
        return (
            "Limited instrument attribution — ensemble-mix cues only (no isolated stem)."
        )
    if not _is_mixed_backing(ctx):
        return "High target attribution (no backing track in this take)."
    return (
        "Limited/moderate target attribution — onset/spectrum/RMS/pitch-class evidence may "
        "partly reflect the backing track as well as the target instrument."
    )


def build_layer_arrangement_context(
    ctx: dict[str, Any] | None,
    *,
    heard_instruments: list[str] | None = None,
) -> str:
    """Describe non-target project instruments as arrangement context only."""
    ctx = dict(ctx or {})
    instruments = [
        str(x).strip() for x in (ctx.get("instruments") or []) if str(x).strip()
    ]
    target = resolve_multitrack_target_layer(ctx)
    mapping = prune_instrument_focuses_to_project(ctx.get("instrument_focuses"), instruments)
    heard = {str(x).strip() for x in (heard_instruments or []) if str(x).strip()}
    if target:
        heard.add(target)

    bits: list[str] = []
    for inst, focuses in mapping.items():
        if not inst or inst == target:
            continue
        if inst in heard:
            continue
        foc_txt = format_focus_list(list(focuses)) if focuses else "(no Practice Focus selected)"
        bits.append(f"{inst} is focused on {foc_txt}")
    if not bits:
        return ""
    roles = "; ".join(bits)
    song_ctx = ctx.get("selected_song_analysis_context")
    if not isinstance(song_ctx, dict):
        song_ctx = {}
    song_name = str(
        song_ctx.get("title") or ctx.get("song") or ctx.get("song_source_name") or ""
    ).strip()
    song_key = str(song_ctx.get("key") or ctx.get("display_key") or "").strip()
    sections = song_ctx.get("sections") or ctx.get("sections") or {}
    form_bit = ""
    if isinstance(sections, dict) and sections:
        from analysis_coach_quality import has_song_form_context

        if has_song_form_context(ctx) or bool(song_ctx.get("has_song_form")):
            names = [str(k).strip() for k in sections.keys() if str(k).strip()]
            if names:
                form_bit = f" in sections such as {', '.join(names[:3])}"
    song_bit = ""
    if song_name:
        song_bit = f" in {song_name}" + (f" ({song_key})" if song_key else "")
    return (
        f"Arrangement context: {roles}. "
        f"Consider how the {target or 'target'} part could leave room for that role"
        f"{song_bit}"
        f"{form_bit}. "
        "Use the known song sections as prospective arrangement context only — "
        "no section-specific performance claim is made without audio↔form timeline alignment. "
        "No audio was scored for those other project instruments."
    )


def _scales_focus_block(
    *,
    target: str,
    features: Any,
    categories: dict[str, Any],
    ctx: dict[str, Any],
    musical_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evidence-based Scales coaching using selected-song harmony + observed pitches."""
    from analysis_coach_quality import has_song_form_context, has_song_harmony_context

    song_ctx = ctx.get("selected_song_analysis_context")
    if not isinstance(song_ctx, dict):
        song_ctx = {}
    song_name = str(
        song_ctx.get("title") or ctx.get("song") or ctx.get("song_source_name") or ""
    ).strip()
    song_key = str(song_ctx.get("key") or ctx.get("display_key") or "").strip()
    chords = [
        str(c).strip()
        for c in (
            song_ctx.get("chord_progression")
            or ctx.get("target_chords")
            or []
        )
        if str(c).strip()
    ]
    sections = song_ctx.get("sections") or ctx.get("sections") or {}
    song_harmony = bool(song_ctx.get("has_song_harmony")) or has_song_harmony_context(ctx)
    song_form = bool(song_ctx.get("has_song_form")) or has_song_form_context(ctx)
    metrics = dict(musical_metrics or {})
    scale_adh = metrics.get("scale_adherence")
    chord_tone = metrics.get("chord_tone_accuracy")
    guide_tone = metrics.get("guide_tone_usage")
    findings: list[str] = []
    mapped = None
    try:
        if scale_adh is not None:
            mapped = int(scale_adh)
    except (TypeError, ValueError):
        mapped = None

    pitch_note = _feature_attr(features, "pitch_note", None)
    if pitch_note:
        findings.append(
            f"Observed center pitch ≈ {pitch_note} (audio statistic — not the selected song key)."
        )

    if song_harmony and (song_key or chords):
        if song_name and song_key:
            findings.append(
                f"Selected song harmonic context: {song_name} in {song_key} (concert/sounding)."
            )
        elif song_key:
            findings.append(f"Selected song key for Scales coaching: {song_key} (concert/sounding).")
        written_label = str(ctx.get("written_key") or "").strip()
        written_map = ctx.get("instrument_written_keys")
        if isinstance(written_map, dict) and target and written_map.get(target):
            written_label = str(written_map.get(target) or written_label).strip()
        concert_label = ""
        try:
            from music_theory import display_key_label

            concert_label = display_key_label(song_key) if song_key else ""
        except Exception:
            concert_label = song_key
        if written_label and concert_label and written_label.lower() != concert_label.lower():
            findings.append(
                f"Musician-facing written key for {target or 'this layer'}: {written_label} "
                "(scoring uses concert harmony; coaching may use written spelling)."
            )
        if chords:
            preview = " → ".join(chords[:6])
            findings.append(f"Chord progression sample used for harmonic fit: {preview}.")
        if song_form and isinstance(sections, dict) and sections:
            findings.append(
                "Form sections available: " + ", ".join(str(k) for k in list(sections.keys())[:5]) + "."
            )
        elif song_harmony and not song_form:
            findings.append(
                "Harmony is a flat progression (no named Verse/Chorus sections) — "
                "coaching uses key/chords only."
            )
        if scale_adh is not None:
            findings.append(
                f"Scale/mode adherence vs selected-song tonal material ≈ {float(scale_adh):.0f}%."
            )
        if chord_tone is not None:
            findings.append(
                f"Harmonic-material overlap with the selected song ≈ {float(chord_tone):.0f}% "
                "(detected pitch classes vs the union of tones from the song's chord symbols — "
                "not a timestamp-aligned chord-by-chord hit rate)."
            )
        if guide_tone is not None:
            findings.append(
                f"Guide-tone material overlap across the selected song harmony ≈ {float(guide_tone):.0f}% "
                "(3rds / encoded 7ths pooled from the progression — not per-active-chord timeline usage)."
            )
        if scale_adh is None and chord_tone is None:
            findings.append(
                "Pitch-class harmonic fit was limited in this take — coach from the selected "
                "song key/chords on the next loop."
            )
        rtype = str(ctx.get("recording_type") or "").strip().lower().replace("_", " ")
        if "backing" in rtype or ctx.get("backing_track_context"):
            findings.append(
                "Mixed-recording caution: pitch-class / scale evidence may include backing-track "
                "content as well as the target instrument."
            )

        if mapped is not None and mapped >= 70:
            went_well = (
                f"{_mixed_backing_subject(ctx, target)} shows strong tonal alignment with "
                f"{song_name or 'the selected song'}'s scale/harmony."
            )
            improve_to = (
                "Tighten weaker chords in the progression — land chord tones that each symbol "
                "actually encodes on strong beats (3rds always; 7ths only when present)."
            )
        elif mapped is not None and mapped >= 50:
            went_well = (
                f"{_mixed_backing_subject(ctx, target)} has usable scale material inside "
                f"{song_name or 'the selected song'}, with room to fit local chords more tightly."
            )
            improve_to = (
                f"Over the next take, outline chord tones of "
                f"{' → '.join(chords[:3]) if chords else song_key} before freer scale runs."
            )
        else:
            went_well = (
                f"{_mixed_backing_subject(ctx, target)} establishes pitch material to reshape toward "
                f"{song_name or 'the selected song'}'s harmony."
            )
            improve_to = (
                "Prioritize chord tones from the selected progression; treat non-chord tones as "
                "approach notes that resolve."
            )
        first_sec = ""
        if song_form and isinstance(sections, dict) and sections:
            first_sec = next((str(k) for k in sections.keys() if str(k).strip()), "")
        if first_sec and chords:
            drill = (
                f"Loop {first_sec} of {song_name or 'the selected song'} @ a slower tempo and "
                f"target the 3rd of each chord in {' → '.join(chords[:4])}."
            )
        elif chords:
            try:
                from recording_analysis import _chord_tone_coaching_hint

                tone_hint = _chord_tone_coaching_hint(chords[:4])
            except Exception:
                tone_hint = "chord tones that appear in each symbol"
            drill = (
                f"Play {' → '.join(chords[:4])} slowly — hold {tone_hint} "
                f"before connecting with {song_key or 'the song'} scale tones."
            )
        else:
            drill = (
                f"Practice the {song_key} scale against the selected song's harmony, resolving "
                "each phrase to a stable chord tone."
            )
        assessment = (
            f"{mapped}/100 (scale adherence vs selected-song tonal material)"
            if mapped is not None
            else "Qualitative Scales read from selected-song harmony + observed pitches"
        )
    else:
        findings.append(
            "No resolved Upload song harmony — Scales coaching stays exercise-oriented "
            "(Other / Not a Song or unresolved source)."
        )
        if pitch_note:
            findings.append(
                "Use a tuner/drone and a chosen exercise key; do not treat the observed "
                "center pitch as a song key."
            )
        went_well = (
            f"{_mixed_backing_subject(ctx, target)} provides pitch material for scale practice."
        )
        improve_to = (
            "Choose an exercise key deliberately, then isolate one scale pattern for an 8-bar loop."
        )
        drill = (
            f"{target or 'Layer'} Scales drill: one octave ascending/descending with even "
            "subdivisions, then resolve to the tonic."
        )
        assessment = "Qualitative Scales coaching (exercise context — no song harmony)"

    # Never import technique long-tone tips as Scales "evidence".
    _ = categories  # reserved for future pitch-category harmonic notes only
    return {
        "focus": "Scales",
        "target_layer": target,
        "assessment": assessment,
        "score": mapped,
        "findings": findings,
        "went_well": went_well,
        "improve_to": improve_to,
        "drill": drill,
    }


def build_target_layer_focus_analysis(
    *,
    features: Any = None,
    scores: dict[str, Any] | None = None,
    categories: dict[str, Any] | None = None,
    ctx: dict[str, Any] | None = None,
    musical_metrics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Explicit per-Focus coaching blocks for the Layer being analyzed.

    Every selected target Practice Focus gets its own section. Non-target instrument
    Focuses are never scored here (they belong in arrangement context only).
    """
    ctx = dict(ctx or {})
    instruments = [
        str(x).strip() for x in (ctx.get("instruments") or []) if str(x).strip()
    ]
    target = resolve_multitrack_target_layer(ctx)
    if target and instruments and target not in instruments:
        # Stale target after project-instrument edit — fall back to first project instrument.
        target = instruments[0]
    mapping = prune_instrument_focuses_to_project(ctx.get("instrument_focuses"), instruments)
    focuses = coerce_focus_list(mapping.get(target) if target else None)
    if not focuses:
        focuses = coerce_focus_list(
            ctx.get("practice_focuses") or ctx.get("focuses") or ctx.get("focus")
        )
    scores = dict(scores or {})
    categories = dict(categories or {})
    blocks: list[dict[str, Any]] = []

    onset_strength = float(_feature_attr(features, "onset_strength_mean", 0.0) or 0.0)
    onset_density = float(_feature_attr(features, "onset_density", 0.0) or 0.0)
    groove = float(_feature_attr(features, "groove_tightness", 0.0) or 0.0)
    centroid = float(_feature_attr(features, "spectral_centroid_mean", 0.0) or 0.0)
    dyn_flat = float(_feature_attr(features, "dyn_flatness", 0.0) or 0.0)
    dyn_range = float(_feature_attr(features, "dyn_range", 0.0) or 0.0)
    pitch_std = _feature_attr(features, "pitch_cents_std", None)
    tech_cat = categories.get("technique") or {}
    tone_cat = categories.get("tone") or {}
    timing_cat = categories.get("timing") or {}
    musicality_cat = categories.get("musicality") or {}

    for focus in focuses:
        fl = focus.lower()
        mapped = _mapped_score_for_focus(focus, scores)
        findings: list[str] = []
        went_well = ""
        improve_to = ""
        drill = ""
        assessment = ""

        if "scale" in fl:
            block = _scales_focus_block(
                target=target,
                features=features,
                categories=categories,
                ctx=ctx,
                musical_metrics=musical_metrics,
            )
            block["focus"] = focus  # preserve user label (Scales / Scale/mode / etc.)
            blocks.append(block)
            continue

        if "articulation" in fl:
            findings.append(
                f"Attack strength mean ≈ {onset_strength:.2f}; attack density ≈ "
                f"{onset_density:.2f} onsets/sec."
            )
            if groove > 0:
                findings.append(
                    f"About {groove * 100:.0f}% of detected attacks sit near the beat grid."
                )
            if onset_strength >= 1.2 and groove >= 0.45:
                went_well = (
                    f"{_mixed_backing_subject(ctx, target)} shows clear, intentional attacks with useful "
                    "contrast between notes."
                )
            elif onset_strength >= 0.8:
                went_well = (
                    f"{_mixed_backing_subject(ctx, target)} produces audible attacks — a usable articulation "
                    "foundation is present."
                )
            else:
                went_well = (
                    f"{_mixed_backing_subject(ctx, target)} has a starting articulation profile, but attacks "
                    "are often soft or blended."
                )
            if onset_strength < 0.9 or groove < 0.4:
                improve_to = (
                    "Increase attack consistency and tonguing/attack clarity — match starts "
                    "across the phrase, then add intentional accent contrast on destination notes."
                )
            else:
                improve_to = (
                    "Shape accent/attack contrast more deliberately: lighter approach notes, "
                    "clearer peaks on phrase destinations."
                )
            drill = (
                f"{target or 'Layer'} articulation drill: one pitch, eight notes — alternate "
                "soft / marked attacks, then mirror the pattern on a short phrase."
            )
            for line in (tech_cat.get("findings") or [])[:2]:
                text = str(line).strip()
                if text and text not in findings and not _is_coaching_advice_line(text):
                    findings.append(text)
            assessment = (
                f"{mapped}/100 (technique proxy from attack clarity)"
                if mapped is not None
                else "Qualitative articulation read from attack clarity"
            )
        elif fl == "tone" or "tone" in fl:
            findings.append(f"Average spectral brightness ≈ {centroid:.0f} Hz.")
            if dyn_flat:
                findings.append(f"Dynamic flatness estimate ≈ {dyn_flat:.2f} (lower often = more contour).")
            if pitch_std is not None:
                try:
                    findings.append(
                        f"Within-note pitch movement ≈ {float(pitch_std):.0f} cents "
                        "(sustain/tone stability cue)."
                    )
                except (TypeError, ValueError):
                    pass
            if mapped is not None and mapped >= 70:
                went_well = (
                    f"{_mixed_backing_subject(ctx, target)} keeps a relatively consistent tone color through "
                    "the take."
                )
            else:
                went_well = (
                    f"{_mixed_backing_subject(ctx, target)} establishes a recognizable tone center to refine."
                )
            if mapped is not None and mapped < 70:
                improve_to = (
                    "Stabilize tone across sustains and register changes — match color from "
                    "note start through release."
                )
            else:
                improve_to = (
                    "Keep tone color even when articulating or changing register; avoid "
                    "brightening only on accents."
                )
            drill = (
                f"{target or 'Layer'} tone drill: long tones at soft / medium / full — same "
                "color, same release, then connect three notes without color jumps."
            )
            for line in (tone_cat.get("findings") or [])[:2]:
                text = str(line).strip()
                if text and text not in findings:
                    findings.append(text)
            assessment = (
                f"{mapped}/100 (tone score from spectral/energy cues)"
                if mapped is not None
                else "Qualitative tone-color read from spectral cues"
            )
        elif "dynamic" in fl:
            # Real RMS/energy contrast only — never borrow Musicality/technique scores.
            mapped = None
            label = _dynamics_qualitative_label(dyn_flatness=dyn_flat, dyn_range=dyn_range)
            findings.append(
                f"Dynamic range (RMS p90−p10) ≈ {dyn_range:.4f}; "
                f"flatness estimate ≈ {dyn_flat:.2f} (lower usually means more contrast)."
            )
            traj = _energy_trajectory_note(features)
            if traj:
                findings.append(traj)
            else:
                findings.append(
                    "Phrase-level loudness contour was limited or too short to summarize confidently."
                )
            if dyn_flat < 0.55 and dyn_range > 0:
                went_well = (
                    f"{_mixed_backing_subject(ctx, target)} shows usable dynamic contrast between softer and "
                    "louder regions."
                )
                improve_to = (
                    "Increase intentional contrast between phrase peaks and releases — plan "
                    "pp/mf/f shapes rather than accidental spikes."
                )
            elif dyn_range > 0:
                went_well = (
                    f"{_mixed_backing_subject(ctx, target)} has some amplitude variation to shape more deliberately."
                )
                improve_to = (
                    "Widen intentional dynamic contrast: softer approaches, fuller phrase peaks, "
                    "and controlled releases."
                )
            else:
                went_well = (
                    f"{_mixed_backing_subject(ctx, target)} holds a steady energy level — a clean base for "
                    "adding contrast."
                )
                improve_to = (
                    "Add intentional crescendo/decrescendo inside phrases while keeping timing "
                    "and tone stable."
                )
            drill = (
                f"{target or 'Layer'} dynamics drill: play the same phrase pp → mf → f while "
                "keeping timing and tone stable."
            )
            assessment = label
        elif "phras" in fl:
            from analysis_coach_quality import has_audio_form_timeline_alignment

            phrase_metrics = _phrase_metric_bundle(musical_metrics)
            phrase_score = _score_phrasing_from_metrics(phrase_metrics)
            mapped = phrase_score  # never Musicality
            # Evidence-only lines from phrase metrics.
            if "phrase_pacing" in phrase_metrics:
                findings.append(
                    f"Phrase pacing ≈ {phrase_metrics['phrase_pacing']:.0f}/100."
                )
            if "phrase_contour_variety" in phrase_metrics:
                findings.append(
                    f"Phrase contour variety ≈ {phrase_metrics['phrase_contour_variety']:.0f}/100."
                )
            if "space_rests" in phrase_metrics:
                findings.append(
                    f"Intentional-space / rest score ≈ {phrase_metrics['space_rests']:.0f}/100."
                )
            if "landing_note_quality" in phrase_metrics:
                findings.append(
                    f"Landing-note quality ≈ {phrase_metrics['landing_note_quality']:.0f}/100."
                )
            traj = _energy_trajectory_note(features)
            if traj:
                findings.append(traj)
            # Optional observed musicality findings — never coaching advice.
            aligned = has_audio_form_timeline_alignment(ctx)
            for text in (musicality_cat.get("findings") or [])[:3]:
                line = str(text).strip()
                if not line or _is_coaching_advice_line(line):
                    continue
                low = line.lower()
                if not aligned and (
                    "after the intro" in low
                    or "into chorus" in low
                    or "into the chorus" in low
                ):
                    line = (
                        line.replace("after the intro", "after the opening portion of the take")
                        .replace("After the intro", "After the opening portion of the take")
                        .replace("into chorus", "later in the take")
                        .replace("into the chorus", "later in the take")
                    )
                if line not in findings:
                    findings.append(line)
            if not findings:
                findings.append(
                    "Limited direct phrase-metric coverage on this take — phrasing coaching stays qualitative."
                )
            assessment, went_well, improve_to = _phrasing_interpretation(
                phrase_metrics, phrase_score
            )
            drill = (
                f"{target or 'Layer'} phrasing drill: 2-bar question → 1 beat rest → "
                "2-bar answer with a related contour."
            )
        elif "ear" in fl and "train" in fl:
            # Ear Training is qualitative unless a dedicated recognition task was captured.
            mapped = None
            song_ctx = ctx.get("selected_song_analysis_context")
            if not isinstance(song_ctx, dict):
                song_ctx = {}
            song_key = str(song_ctx.get("key") or ctx.get("display_key") or "").strip() or "the song key"
            chords = [
                str(c).strip()
                for c in (song_ctx.get("chord_progression") or ctx.get("target_chords") or [])
                if str(c).strip()
            ]
            chord_bit = " → ".join(chords[:4]) if chords else song_key
            findings = [
                "Limited direct Ear Training evidence from this recording.",
                "The take provides pitch/harmonic material that can support an ear-training exercise.",
                "No dedicated call-and-response / pitch-recognition / interval-matching task was captured.",
            ]
            went_well = ""
            improve_to = (
                "This take does not directly measure Ear Training strongly enough for a numeric score. "
                "Use a short sing-then-play recognition loop next."
            )
            drill = (
                f"Ear Training drill: sing then play scale degrees in {song_key}; "
                f"hear-and-match 1–3–5–7; sing chord roots of {chord_bit} before playing; "
                "identify whether a target note is root / 3rd / 5th against a held chord."
            )
            assessment = "Limited direct evidence — qualitative Ear Training coaching (no numeric meter)"
        elif "timing" in fl or "rhythm" in fl or "groove" in fl:
            from analysis_coach_quality import (
                meter_aware_groove_click_tip,
                resolve_analysis_meter,
                instrument_family,
            )

            findings.extend(str(x) for x in (timing_cat.get("findings") or [])[:3])
            if groove:
                findings.append(f"Groove tightness estimate ≈ {groove * 100:.0f}%.")
            went_well = (
                f"{_mixed_backing_subject(ctx, target)} locks usefully with the pulse."
                if (mapped or 0) >= 65
                else f"{_mixed_backing_subject(ctx, target)} has a rhythmic outline to tighten."
            )
            improve_to = (
                "Place entrances and releases more deliberately against the grid or click."
            )
            drill = meter_aware_groove_click_tip(
                resolve_analysis_meter(ctx),
                family=instrument_family(str(target or ctx.get("instrument") or "")),
            )
            assessment = (
                f"{mapped}/100 (timing/groove proxy)"
                if mapped is not None
                else "Qualitative rhythm/timing read"
            )

        elif "breath" in fl:
            # Acoustic sustain proxies — never treat selection metadata or attack
            # density as Breath Support evidence.
            mapped = None
            energy_note = _energy_trajectory_note(features)
            sustain_bits: list[str] = []
            if dyn_flat:
                sustain_bits.append(
                    f"Acoustic sustain flatness estimate ≈ {dyn_flat:.2f} "
                    "(lower often means more energy contour through held tones)."
                )
            if dyn_range > 0:
                sustain_bits.append(
                    f"RMS energy span ≈ {dyn_range:.4f} "
                    "(proxy for support contrast across the take)."
                )
            if pitch_std is not None:
                try:
                    sustain_bits.append(
                        f"Within-note pitch movement ≈ {float(pitch_std):.0f} cents "
                        "(acoustic cue for support/center through sustains)."
                    )
                except (TypeError, ValueError):
                    pass
            if energy_note:
                sustain_bits.append(energy_note)
            if sustain_bits:
                findings.extend(sustain_bits)
                findings.append(
                    "These are acoustic sustain/energy/pitch cues related to Breath Support — "
                    "not a direct measurement of breathing physiology."
                )
                assessment = (
                    "Inferred from acoustic sustain cues "
                    "(limited direct Breath Support meter)"
                )
                pitch_ok = True
                try:
                    if pitch_std is not None:
                        pitch_ok = float(pitch_std) < 35
                except (TypeError, ValueError):
                    pitch_ok = True
                if dyn_flat and dyn_flat < 0.55 and pitch_ok:
                    went_well = (
                        f"{_mixed_backing_subject(ctx, target)} shows usable acoustic sustain "
                        "stability through held tones."
                    )
                    improve_to = (
                        "Keep air/support steady through releases — avoid energy collapse on "
                        "final notes of longer phrases."
                    )
                else:
                    went_well = (
                        f"{_mixed_backing_subject(ctx, target)} provides usable sustain/energy "
                        "material to coach Breath Support from."
                    )
                    improve_to = (
                        "Aim for steadier acoustic sustain through phrase endings — support "
                        "the release instead of tapering into pitch or energy collapse."
                    )
            else:
                findings = [
                    "Limited direct Breath Support evidence from this recording.",
                    "The take provides sustain/pitch/energy cues related to breath support, "
                    "but breath support itself is inferred rather than directly measured.",
                    "Onset/attack metrics alone are not treated as Breath Support evidence.",
                ]
                went_well = ""
                improve_to = (
                    "This take does not measure Breath Support strongly enough for a numeric score. "
                    "Use a long-tone support loop next."
                )
                assessment = (
                    "Limited direct evidence — qualitative Breath Support coaching "
                    "(no numeric meter)"
                )
            target_l = str(target or "").lower()
            if "flute" in target_l:
                drill = (
                    f"{target or 'Flute'} Breath Support drill: sustain one tone for 8 beats "
                    "through the release without energy collapse; then crescendo → decrescendo "
                    "on one pitch while keeping center; finish with a 4-bar phrase on one breath "
                    "with steady tone through the final release."
                )
            else:
                drill = (
                    f"{target or 'Layer'} Breath Support drill: long tone 8 beats through the "
                    "release without energy collapse; then crescendo → decrescendo on one pitch "
                    "with stable center; finish with a short phrase on one breath through the last note."
                )

        else:
            # Generic Focus: still explicit, without inventing unsupported scores.
            went_well = (
                f"{_mixed_backing_subject(ctx, target)} was analyzed with {focus} as an explicit coaching goal."
            )
            improve_to = (
                f"On the next take, isolate {focus} for one deliberate 8-bar loop before free playing."
            )
            drill = (
                f"{target or 'Layer'} {focus} drill: one short loop focusing only on {focus}, "
                "then re-record."
            )
            assessment = (
                f"{mapped}/100 (nearest related performance score)"
                if mapped is not None
                else f"Qualitative {focus} coaching (no dedicated numeric meter)"
            )
            # Pull related observed findings only — never coaching tips into detected evidence.
            for cat in (tech_cat, tone_cat, timing_cat, musicality_cat):
                for tip in (cat.get("findings") or [])[:1]:
                    text = str(tip).strip()
                    if text and not _is_coaching_advice_line(text):
                        findings.append(text)
                        break
                if findings:
                    break

        blocks.append(
            {
                "focus": focus,
                "target_layer": target,
                "assessment": assessment,
                "score": mapped,
                "findings": findings,
                "went_well": went_well,
                "improve_to": improve_to,
                "drill": drill,
            }
        )
    for block in blocks:
        if not isinstance(block, dict):
            continue
        fl = str(block.get("focus") or "").lower()
        family = (
            "scales" if "scale" in fl else
            "tone" if "tone" in fl else
            "articulation" if "articulation" in fl else
            "dynamics" if "dynamic" in fl else
            "general"
        )
        block["attribution_confidence"] = _mixed_attribution_confidence(ctx, family=family)
        if _is_mixed_backing(ctx):
            findings = list(block.get("findings") or [])
            if not any("mixed" in str(x).lower() or "backing" in str(x).lower() for x in findings):
                findings.append(
                    "Mixed-recording note: treat target-instrument attribution with limited "
                    "confidence unless an isolated stem is available."
                )
            block["findings"] = findings

    return blocks


def enrich_layer_analysis_result(
    result: dict[str, Any],
    ctx: dict[str, Any],
    *,
    uploaded_track_count: int = 1,
) -> dict[str, Any]:
    """Stamp Layer ownership fields, Focus blocks, and stem-aware plan tips."""
    out = dict(result or {})
    ctx = dict(ctx or {})
    instruments = [
        str(x).strip() for x in (ctx.get("instruments") or out.get("instruments") or []) if str(x).strip()
    ]
    target = resolve_multitrack_target_layer(ctx)
    if target and instruments and target not in instruments:
        target = instruments[0]
        ctx["target_layer"] = target
    mapping = prune_instrument_focuses_to_project(ctx.get("instrument_focuses"), instruments)
    ctx["instruments"] = instruments
    ctx["instrument_focuses"] = mapping
    target_focuses = coerce_focus_list(mapping.get(target) if target else None)
    if not target_focuses:
        target_focuses = coerce_focus_list(
            out.get("practice_focuses")
            or ctx.get("practice_focuses")
            or ctx.get("focuses")
        )
        # If legacy focuses came from a stale instrument, keep only when target is current.
        if target and instruments and target not in instruments:
            target_focuses = []

    out["multitrack"] = True
    out["multitrack_mode"] = "layer"
    out["target_layer"] = target
    out["instruments"] = instruments
    out["instrument_focuses"] = dict(mapping)
    out["practice_focuses"] = list(target_focuses)
    out["uploaded_track_count"] = int(uploaded_track_count or 1)
    out["comparison_stem_count"] = int(uploaded_track_count or 1)

    if out.get("ok"):
        blocks = build_target_layer_focus_analysis(
            features=out.get("features"),
            scores=out.get("scores") or {},
            categories=out.get("categories") or {},
            ctx=ctx,
            musical_metrics=out.get("musical_metrics") or {},
        )
        out["target_layer_focus_analysis"] = blocks
        arrangement = build_layer_arrangement_context(ctx, heard_instruments=[target] if target else [])
        out["layer_arrangement_context"] = arrangement

        song_ctx = ctx.get("selected_song_analysis_context")
        if not isinstance(song_ctx, dict):
            song_ctx = {}
        out["selected_song_analysis_context"] = dict(song_ctx) if song_ctx else out.get("selected_song_analysis_context")
        song_name = str(
            (song_ctx or {}).get("title") or ctx.get("song") or ctx.get("song_source_name") or ""
        ).strip()
        song_key = str((song_ctx or {}).get("key") or ctx.get("display_key") or "").strip()
        ref_bpm = (song_ctx or {}).get("bpm")
        if ref_bpm in (None, ""):
            ref_bpm = ctx.get("reference_bpm") or ctx.get("practice_bpm")
        meter = str((song_ctx or {}).get("meter") or ctx.get("time_signature") or "").strip()

        # Prefixed summary ownership — analyzed target + selected song authority.
        focus_txt = format_focus_list(target_focuses) if target_focuses else "selected Practice Focuses"
        ownership = (
            f"Multitrack Layer — analyzing {target or 'the uploaded part'} only "
            f"(Practice Focuses: {focus_txt})."
        )
        if song_name:
            song_line = f"Song context: {song_name}"
            if song_key:
                song_line += f" — {song_key}"
            if meter:
                song_line += f", {meter}"
            if ref_bpm not in (None, ""):
                try:
                    song_line += f", reference tempo {int(float(ref_bpm))} BPM"
                except (TypeError, ValueError):
                    song_line += f", reference tempo {ref_bpm}"
            song_line += "."
            ownership = (
                f"Analyzing your {target or 'uploaded'} layer in {song_name}. {ownership} {song_line}"
            )
        summary = str(out.get("coach_summary") or "").strip()
        # Dedupe: Single-path coach summary may already include a Song context line.
        import re as _re
        summary = _re.sub(
            r"(?i)\s*Song context:[^.]*\.\s*",
            " ",
            summary,
        ).strip()
        if "analyzing your" not in summary.lower() and ownership.lower() not in summary.lower():
            out["coach_summary"] = f"{ownership} {summary}".strip()
        elif ownership.lower() not in summary.lower():
            out["coach_summary"] = f"{ownership} {summary}".strip()
        if arrangement:
            # Keep arrangement as its own field; also append once to summary if absent.
            if "arrangement context:" not in summary.lower():
                out["coach_summary"] = (
                    f"{out.get('coach_summary', '').rstrip()} {arrangement}"
                ).strip()

        # Gate "mute other stems" when comparison stems were not uploaded.
        plan = [str(x).strip() for x in (out.get("practice_plan") or []) if str(x).strip()]
        cleaned: list[str] = []
        for tip in plan:
            low = tip.lower()
            if "mute other stems" in low or (
                "other stems" in low and int(uploaded_track_count or 1) < 2
            ):
                if int(uploaded_track_count or 1) >= 2:
                    cleaned.append(tip)
                else:
                    cleaned.append(
                        "Practice entrances/releases against a click or project reference track "
                        "(no other stems were uploaded for this Layer take)."
                    )
            else:
                cleaned.append(tip)
        if int(uploaded_track_count or 1) < 2:
            # Ensure a stem-free Layer tip exists even if the plan was built without the Layer branch.
            if not any("click" in t.lower() or "reference track" in t.lower() for t in cleaned):
                cleaned.insert(
                    0,
                    "Practice entrances/releases against a click or project reference track.",
                )
        out["practice_plan"] = cleaned

        # Never invent heard-performance claims for non-target instruments.
        out["non_target_instruments_scored"] = False
    return out


def validate_multitrack_analyze_request(
    *,
    recording_type: Any,
    file_count: int,
    instruments: list[str] | None = None,
    target_layer: str | None = None,
) -> str | None:
    """Return a user-visible validation message, or None when analysis may proceed.

    Contracts
    ---------
    Multitrack Layer
        - At least one selected instrument
        - A target layer instrument (explicit or first selected)
        - Exactly one uploaded audio file for that target layer is enough

    Multitrack Mix
        - At least one selected instrument (ensemble context)
        - One uploaded mix file is enough, OR 2+ stem files for layer comparison
    """
    instruments = [str(x).strip() for x in (instruments or []) if str(x).strip()]
    target = str(target_layer or "").strip()
    n = int(file_count or 0)
    rtype = str(recording_type or "").strip() or RECORDING_TYPE_MT_MIX

    if n <= 0:
        if is_multitrack_layer_type(rtype):
            return "Upload an audio file for the target layer before analyzing."
        return "Upload the ensemble mix recording (or 2+ stems) before analyzing."

    if not instruments:
        return "Select at least one instrument in Step 1 before analyzing."

    if is_multitrack_layer_type(rtype):
        if not target:
            return "Choose the target layer instrument before analyzing."
        if target not in instruments:
            return (
                f"Target layer “{target}” must be one of the selected instruments "
                f"({', '.join(instruments)})."
            )
        # One file is enough for Layer.
        return None

    # Mix — one mix file OR 2+ stems.
    if n >= 1:
        return None
    return "Upload the ensemble mix recording (or 2+ stems) before analyzing."


def assign_instruments_to_tracks(
    tracks: list[dict[str, Any]],
    *,
    instruments: list[str],
    target_layer: str = "",
    recording_type: Any = None,
) -> list[dict[str, Any]]:
    """Attach instrument labels to uploaded files for coaching context."""
    instruments = [str(x).strip() for x in instruments if str(x).strip()]
    target = str(target_layer or "").strip()
    out: list[dict[str, Any]] = []
    for i, tr in enumerate(tracks):
        row = dict(tr)
        if not str(row.get("instrument") or "").strip():
            if is_multitrack_layer_type(recording_type) and target:
                row["instrument"] = target
            elif i < len(instruments):
                row["instrument"] = instruments[i]
            elif instruments:
                row["instrument"] = instruments[0]
        if not str(row.get("name") or "").strip():
            row["name"] = str(row.get("instrument") or row.get("filename") or f"Track {i + 1}")
        out.append(row)
    return out



def build_mix_focus_analysis(
    *,
    features: Any = None,
    scores: dict[str, Any] | None = None,
    categories: dict[str, Any] | None = None,
    ctx: dict[str, Any] | None = None,
    musical_metrics: dict[str, Any] | None = None,
    uploaded_track_count: int = 1,
) -> list[dict[str, Any]]:
    """Practice Focus blocks for every Mix instrument mapping.

    One mixed file => limited attribution. Multiple stems => stronger per-instrument evidence.
    """
    ctx = dict(ctx or {})
    instruments = [str(x).strip() for x in (ctx.get("instruments") or []) if str(x).strip()]
    mapping = prune_instrument_focuses_to_project(ctx.get("instrument_focuses"), instruments)
    isolated = _mix_has_isolated_stems(ctx, uploaded_track_count=uploaded_track_count)
    scores = dict(scores or {})
    categories = dict(categories or {})
    blocks: list[dict[str, Any]] = []

    for inst in instruments:
        focuses = coerce_focus_list(mapping.get(inst))
        if not focuses:
            continue
        layer_ctx = dict(ctx)
        layer_ctx["target_layer"] = inst
        layer_ctx["instrument_focuses"] = {inst: list(focuses)}
        layer_ctx["practice_focuses"] = list(focuses)
        layer_ctx["uploaded_track_count"] = int(uploaded_track_count or 1)
        # For a single mixed file, force limited-attribution wording even without backing track.
        if not isolated:
            layer_ctx["backing_track_context"] = True
            layer_ctx["mix_polyphony_limited_attribution"] = True
        layer_blocks = build_target_layer_focus_analysis(
            features=features,
            scores=scores,
            categories=categories,
            ctx=layer_ctx,
            musical_metrics=musical_metrics,
        )
        for block in layer_blocks:
            if not isinstance(block, dict):
                continue
            row = dict(block)
            row["instrument"] = inst
            row["target_layer"] = inst
            if not isolated:
                row["attribution_confidence"] = (
                    "Limited instrument attribution — one mixed ensemble file without "
                    "isolated stems; avoid treating this as a definitive solo-instrument score."
                )
                # Soften definitive instrument-subject claims.
                findings = []
                for line in list(row.get("findings") or []):
                    text = str(line).strip()
                    if not text:
                        continue
                    low = text.lower()
                    if low.startswith(inst.lower() + " "):
                        text = (
                            f"Where {inst} is prominent in the ensemble mix, "
                            + text[len(inst) :].strip()
                        )
                    elif "high target attribution" in low:
                        continue
                    findings.append(text)
                findings.insert(
                    0,
                    f"{inst} Focus `{row.get('focus')}` is coached from ensemble-mix cues "
                    "(no isolated stem for this part).",
                )
                row["findings"] = findings
                went = str(row.get("went_well") or "").strip()
                if went and went.lower().startswith(inst.lower()):
                    row["went_well"] = (
                        f"Attack/spectral evidence in the ensemble mix suggests: "
                        + went[len(inst) :].lstrip(" :,-")
                    )
                # One-file Mix: keep numeric cue as supporting mix proxy, not an instrument grade.
                raw_assess = str(row.get("assessment") or "")
                proxy_score = row.get("score")
                if proxy_score is None:
                    m = re.search(r"(\d{1,3})\s*/\s*100", raw_assess)
                    if m:
                        try:
                            proxy_score = int(m.group(1))
                        except ValueError:
                            proxy_score = None
                focus_l = str(row.get("focus") or "").lower()
                if "articul" in focus_l:
                    proxy_label = "attack-clarity proxy"
                    assessment = "Mix-level proxy / limited instrument attribution"
                elif "tone" in focus_l:
                    proxy_label = "mix-spectrum / tone-color proxy"
                    assessment = "Mix-level spectral proxy / limited instrument attribution"
                elif "rhythm" in focus_l or "groove" in focus_l or "comp" in focus_l:
                    proxy_label = "ensemble groove / pulse proxy"
                    assessment = "Mix-level groove proxy / limited attribution"
                else:
                    proxy_label = "ensemble mix proxy"
                    assessment = "Mix-level proxy / limited instrument attribution"
                row["assessment"] = assessment
                row["score"] = None
                row["display_as_instrument_score"] = False
                row["mix_proxy_label"] = proxy_label
                row["mix_proxy_score"] = proxy_score
                if proxy_score is not None:
                    cue = f"Relevant mix cue: {proxy_label} = {int(proxy_score)}/100 (ensemble evidence, not an isolated {inst} grade)."
                    findings = list(row.get("findings") or [])
                    if not any("relevant mix cue" in str(x).lower() for x in findings):
                        findings.append(cue)
                    row["findings"] = findings
                row["attribution_scope"] = "mix_limited"
            else:
                row["attribution_scope"] = "stem"
            blocks.append(row)
    return blocks


def build_ensemble_mix_analysis(
    *,
    features: Any = None,
    scores: dict[str, Any] | None = None,
    ctx: dict[str, Any] | None = None,
    uploaded_track_count: int = 1,
    stem_comparisons: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """First-class ensemble Mix analysis section."""
    import re

    ctx = dict(ctx or {})
    scores = dict(scores or {})
    isolated = _mix_has_isolated_stems(ctx, uploaded_track_count=uploaded_track_count)
    instruments = [str(x).strip() for x in (ctx.get("instruments") or []) if str(x).strip()]

    onset_strength = float(_feature_attr(features, "onset_strength_mean", 0.0) or 0.0)
    onset_density = float(_feature_attr(features, "onset_density", 0.0) or 0.0)
    groove = float(_feature_attr(features, "groove_tightness", 0.0) or 0.0)
    centroid = float(_feature_attr(features, "spectral_centroid_mean", 0.0) or 0.0)
    dyn_flat = float(_feature_attr(features, "dyn_flatness", 0.0) or 0.0)
    dyn_range = float(_feature_attr(features, "dyn_range", 0.0) or 0.0)
    energy_note = _energy_trajectory_note(features)

    timing_bits = [
        f"Pulse/onset density in the ensemble mix ≈ {onset_density:.2f}/sec.",
        f"Onset strength mean ≈ {onset_strength:.2f} (attack clustering proxy).",
    ]
    if scores.get("timing") is not None:
        try:
            timing_bits.append(
                f"Timing cohesion mix-level estimate: {int(scores.get('timing'))}/100."
            )
        except (TypeError, ValueError):
            pass

    groove_bits: list[str] = []
    if groove > 0:
        groove_bits.append(
            f"Groove cohesion proxy: ~{groove * 100:.0f}% of mix onsets near the beat grid."
        )
    if scores.get("groove") is not None:
        try:
            groove_bits.append(
                f"Groove mix-level estimate: {int(scores.get('groove'))}/100."
            )
        except (TypeError, ValueError):
            pass
    meter = str(ctx.get("time_signature") or "").strip()
    song_ctx = ctx.get("selected_song_analysis_context")
    if isinstance(song_ctx, dict):
        meter = str(song_ctx.get("meter") or meter).strip()
    if meter:
        groove_bits.append(f"Meter context for feel coaching: {meter}.")

    if isolated and stem_comparisons:
        balance_bits = [
            "Relative stem levels / timing offsets are available from labeled uploads."
        ]
        for row in list(stem_comparisons or [])[:6]:
            if isinstance(row, dict):
                bit = str(row.get("summary") or row.get("finding") or "").strip()
                if bit:
                    balance_bits.append(bit)
        balance_note = "Stem-aware balance: compare RMS/presence across labeled parts."
    else:
        balance_bits = [
            f"Global mix spectral centroid ≈ {centroid:.0f} Hz (broad spectral balance proxy).",
            f"Mix dynamic flatness ≈ {dyn_flat:.2f}; RMS span ≈ {dyn_range:.3f}.",
            "Cannot claim per-instrument level differences without isolated stems or source separation.",
        ]
        balance_note = (
            "One mixed file: broad mix balance proxies only — not per-instrument faders."
        )

    interaction_bits = [
        f"Simultaneous onset density proxy ≈ {onset_density:.2f}/sec — denser mixes leave less space.",
    ]
    if isolated:
        interaction_bits.append(
            "Stem uploads allow comparing entrances/releases and overlap between parts."
        )
    else:
        interaction_bits.append(
            "Interaction/space coaching uses ensemble density and rests; it does not invent "
            "isolated instrument behavior from a single blended file."
        )

    shape_bits: list[str] = []
    if energy_note:
        shape_bits.append(str(energy_note))
    if scores.get("musicality") is not None:
        try:
            shape_bits.append(
                f"Musical shape / arc mix-level estimate: {int(scores.get('musicality'))}/100."
            )
        except (TypeError, ValueError):
            pass

    return {
        "title": "Ensemble Mix analysis",
        "input_mode": "stems" if isolated else "single_mix_file",
        "instruments": instruments,
        "timing_cohesion": timing_bits,
        "groove_cohesion": groove_bits,
        "balance": balance_bits,
        "balance_policy": balance_note,
        "interaction_space": interaction_bits,
        "musical_shape": shape_bits,
    }



def _build_mix_practice_plan(
    *,
    ctx: dict[str, Any],
    mapping: dict[str, list[str]],
    instruments: list[str],
    isolated: bool,
    existing_plan: list[str] | None = None,
) -> list[str]:
    """Ensemble-first Mix practice plan that preserves every instrument→Focus mapping."""
    meter = str(ctx.get("time_signature") or "").strip()
    song_ctx = ctx.get("selected_song_analysis_context")
    if isinstance(song_ctx, dict):
        meter = str(song_ctx.get("meter") or meter).strip()
    ref_bpm = None
    if isinstance(song_ctx, dict):
        ref_bpm = song_ctx.get("bpm")
    if ref_bpm in (None, ""):
        ref_bpm = ctx.get("reference_bpm") or ctx.get("practice_bpm")
    try:
        bpm_txt = str(int(float(ref_bpm))) if ref_bpm not in (None, "") else "practice"
    except (TypeError, ValueError):
        bpm_txt = "practice"

    plan: list[str] = []
    # A) Ensemble
    if "6/8" in meter.replace(" ", "") or meter.strip() == "6/8":
        plan.append(
            f"ENSEMBLE: loop 8 bars near {bpm_txt} BPM and lock the two big 6/8 pulses — "
            "listen for blend, space, and shared pocket (not isolated-part timing claims)."
        )
    else:
        plan.append(
            f"ENSEMBLE: loop 8 bars near {bpm_txt} BPM focusing on shared pulse, balance, "
            "and arrangement space across the Mix."
        )

    # B/C) Every instrument → Focus mapping
    mapping_bits = []
    for inst in instruments:
        focs = coerce_focus_list(mapping.get(inst))
        if focs:
            mapping_bits.append(f"{inst} → {format_focus_list(focs)}")
            for foc in focs:
                fl = foc.lower()
                if "articul" in fl:
                    plan.append(
                        f"{inst}: {foc} — lighter destination-aware attacks in the blend; "
                        "confirm later with a short isolated take if needed."
                    )
                elif "tone" in fl:
                    plan.append(
                        f"{inst}: {foc} — keep color steady through the phrase while leaving "
                        "spectral space in the Mix."
                    )
                elif "rhythm" in fl or "groove" in fl or "comp" in fl:
                    if not isolated:
                        plan.append(
                            f"{inst}: {foc} role — simplify the pattern and lock the main pulses "
                            "while leaving space for the other part (role-aware Mix coaching, "
                            "not a claim of isolated strumming errors)."
                        )
                    else:
                        plan.append(
                            f"{inst}: {foc} — lock the rhythm pattern to the grid and check "
                            "stem timing against the ensemble."
                        )
                else:
                    plan.append(f"{inst}: keep Focus `{foc}` visible for one intentional Mix loop.")
        else:
            mapping_bits.append(f"{inst} → (no Practice Focus selected)")
    if mapping_bits:
        plan.insert(1, "Practice Focuses: " + "; ".join(mapping_bits) + ".")

    # Keep useful non-conflicting tips from the existing plan (song/harmony), drop leaks.
    leak_tokens = (
        "breath support",
        "breath-controlled",
        "embouchure",
        "mute other stems",
        "practice focuses (",
    )
    for tip in existing_plan or []:
        low = str(tip).lower().strip()
        if not low:
            continue
        if any(t in low for t in leak_tokens):
            continue
        if low.startswith("ensemble:") or low.startswith("practice focuses:"):
            continue
        # Avoid duplicating instrument Focus lines we already generated.
        if any(low.startswith(f"{inst.lower()}:") for inst in instruments):
            continue
        if tip not in plan:
            plan.append(tip)

    # Dedupe while preserving order
    out: list[str] = []
    seen: set[str] = set()
    for tip in plan:
        key = tip.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(tip)
    return out[:10]



def enrich_mix_analysis_result(
    result: dict[str, Any],
    ctx: dict[str, Any],
    *,
    uploaded_track_count: int = 1,
    stem_comparisons: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Stamp Mix ownership: all instruments, ensemble-first summary, limited attribution."""
    import re

    out = dict(result or {})
    ctx = dict(ctx or {})
    instruments = [
        str(x).strip()
        for x in (ctx.get("instruments") or out.get("instruments") or [])
        if str(x).strip()
    ]
    mapping = prune_instrument_focuses_to_project(ctx.get("instrument_focuses"), instruments)
    ctx["instruments"] = instruments
    ctx["instrument_focuses"] = mapping
    ctx["recording_type"] = str(
        ctx.get("recording_type") or out.get("recording_type") or RECORDING_TYPE_MT_MIX
    )
    ctx["uploaded_track_count"] = int(uploaded_track_count or 1)
    isolated = _mix_has_isolated_stems(ctx, uploaded_track_count=uploaded_track_count)

    out["multitrack"] = True
    out["multitrack_mode"] = "mix_stems" if isolated else "mix_single"
    out["recording_type"] = ctx["recording_type"]
    out["instruments"] = instruments
    out["instrument_focuses"] = dict(mapping)
    flat_focuses: list[str] = []
    for inst in instruments:
        for foc in coerce_focus_list(mapping.get(inst)):
            label = f"{inst} → {foc}"
            if label not in flat_focuses:
                flat_focuses.append(label)
    out["practice_focuses"] = list(flat_focuses)
    out["uploaded_track_count"] = int(uploaded_track_count or 1)
    out["has_isolated_stems"] = isolated
    out["mix_evidence_mode"] = "stems" if isolated else "single_mix_file"
    out.pop("target_layer", None)
    out["instrument"] = "Multitrack Mix"
    out["instrument_display"] = (
        "Multitrack Mix — " + " + ".join(instruments) if instruments else "Multitrack Mix"
    )

    if not out.get("ok"):
        return out

    blocks = build_mix_focus_analysis(
        features=out.get("features"),
        scores=out.get("scores") or {},
        categories=out.get("categories") or {},
        ctx=ctx,
        musical_metrics=out.get("musical_metrics") or {},
        uploaded_track_count=uploaded_track_count,
    )
    out["practice_focus_analysis"] = blocks
    out["target_layer_focus_analysis"] = blocks
    out["mix_focus_analysis"] = blocks

    ensemble = build_ensemble_mix_analysis(
        features=out.get("features"),
        scores=out.get("scores") or {},
        ctx=ctx,
        uploaded_track_count=uploaded_track_count,
        stem_comparisons=stem_comparisons or out.get("stem_comparisons"),
    )
    out["ensemble_mix_analysis"] = ensemble

    cats = dict(out.get("categories") or {})
    if not isolated:
        for key, cat in list(cats.items()):
            if not isinstance(cat, dict):
                continue
            cat = dict(cat)
            title = str(cat.get("title") or key)
            if key in {"pitch", "tone", "technique"}:
                cat["title"] = f"{title} (mix-level estimate)"
                findings = [str(x) for x in (cat.get("findings") or []) if str(x).strip()]
                softened: list[str] = []
                for line in findings:
                    low = line.lower()
                    if any(inst.lower() in low for inst in instruments):
                        softened.append(
                            "Mix evidence: "
                            + line
                            + " — limited instrument attribution without isolated stems."
                        )
                    elif "brightness" in low or "spectral" in low:
                        if "mix spectral" in low or "mix spectrum" in low:
                            softened.append(line)
                        else:
                            softened.append(
                                "Mix spectral evidence: " + line
                            )
                    else:
                        softened.append(line)
                if key == "pitch":
                    softened.insert(
                        0,
                        "Pitch/F0 evidence is lower-confidence in a polyphonic mix and is not "
                        "treated as a definitive instrument-specific intonation score.",
                    )
                if key == "tone":
                    softened.insert(
                        0,
                        "Spectral centroid/brightness here describes the MIX spectrum, "
                        "not an isolated instrument tone.",
                    )
                if key == "technique":
                    softened.insert(
                        0,
                        "Technique deep-dive uses ensemble/mix attack evidence — not a "
                        "hidden single-instrument technique grade.",
                    )
                cat["findings"] = softened
            cats[key] = cat
        out["categories"] = cats
        out["score_scope"] = "mix_level_estimates"
        out["pitch_evidence_limited"] = True

        # Rewrite global deep-dive tips to stay Mix-owned (no Flute/Guitar leakage).
        for key, cat in list(cats.items()):
            if not isinstance(cat, dict):
                continue
            cat = dict(cat)
            tips = [str(x).strip() for x in (cat.get("tips") or []) if str(x).strip()]
            findings = [str(x).strip() for x in (cat.get("findings") or []) if str(x).strip()]
            if key == "pitch":
                findings = [
                    x for x in findings
                    if not any(
                        t in x.lower()
                        for t in ("embouchure", "flute intonation", "air stream", "aperture")
                    )
                ]
                if not any("polyphonic" in x.lower() or "lower-confidence" in x.lower() for x in findings):
                    findings.insert(
                        0,
                        "Polyphonic pitch/F0 evidence is ambiguous in this blended Mix and is "
                        "not used for isolated-instrument intonation diagnosis.",
                    )
                tips = [
                    "Use a solo re-recording or labeled stem for instrument-specific intonation work.",
                    "In Mix mode, treat global F0 as ensemble pitch clutter/risk — not an isolated-instrument intonation diagnosis.",
                    "For song-key center checks, isolate one part at a time against a drone.",
                ]
            elif key == "technique":
                findings = [
                    x for x in findings
                    if not any(
                        t in x.lower()
                        for t in ("flute attack", "tonguing", "embouchure", "register transition")
                    )
                ]
                if not any("ensemble" in x.lower() or "mix attack" in x.lower() for x in findings):
                    findings.insert(
                        0,
                        "Global onset/attack evidence here describes ensemble/mix clarity and density, "
                        "not a hidden Flute technique grade.",
                    )
                tips = [
                    "Listen for whether attack clustering creates clutter or locks the pocket.",
                    "Simplify overlapping entrances so onsets read cleanly in the blend.",
                    "Keep instrument-specific articulation micro-drills under each instrument Focus card; keep this section Mix-level.",
                ]
            elif key == "tone":
                tips = [
                    "Listen for whether the overall blend stays balanced in brightness and density across the phrase.",
                    "If one color dominates the Mix spectrum, rebalance arrangement space rather than chasing a solo-tone fix here.",
                    "Instrument-specific tone color work belongs under each instrument Focus card.",
                ]
            cat["findings"] = findings
            cat["tips"] = tips
            cats[key] = cat
        out["categories"] = cats

        scores = dict(out.get("scores") or {})
        ranked = sorted(
            ((k, int(v)) for k, v in scores.items() if isinstance(v, (int, float))),
            key=lambda kv: kv[1],
        )
        # Prefer reliable ensemble families; do not force Confidence as biggest weakness.
        unsafe = {"pitch", "tone", "technique", "confidence"}
        safe = [kv for kv in ranked if kv[0] not in unsafe]
        prefer = [kv for kv in safe if kv[0] in {"timing", "groove", "musicality"}]
        pick = prefer or safe
        if pick:
            growth_name, growth_score = pick[0]
            label_map = {
                "timing": "timing cohesion",
                "groove": "groove cohesion",
                "musicality": "musical shape",
            }
            growth_l = label_map.get(growth_name, growth_name)
            # Only promote a scored growth edge when the estimate is clearly soft (< 70).
            if growth_score < 70:
                out["biggest_issue"] = (
                    f"{growth_l} (mix-level estimate {growth_score}/100)."
                )
                out["next_focus"] = (
                    f"Most reliable ensemble opportunity: tighten {growth_l} while preserving "
                    "musical shape and arrangement space."
                )
            else:
                out["biggest_issue"] = (
                    "No single instrument-specific weakness is assigned from this blended file; "
                    "prioritize ensemble timing, groove, and interaction."
                )
                out["next_focus"] = (
                    "Most reliable ensemble opportunity: tighten groove/interaction while "
                    "preserving the strong musical shape."
                )
        else:
            out["biggest_issue"] = (
                "No single instrument-specific weakness is assigned from this blended file; "
                "prioritize ensemble timing, groove, and interaction."
            )
            out["next_focus"] = (
                "Most reliable ensemble opportunity: tighten groove/interaction while "
                "preserving arrangement space."
            )

        # Rebuild Recommended next practice: ensemble-first + all instrument→Focus mappings.
        out["practice_plan"] = _build_mix_practice_plan(
            ctx=ctx,
            mapping=mapping,
            instruments=instruments,
            isolated=isolated,
            existing_plan=list(out.get("practice_plan") or []),
        )

    song_ctx = ctx.get("selected_song_analysis_context")
    if not isinstance(song_ctx, dict):
        song_ctx = {}
    out["selected_song_analysis_context"] = (
        dict(song_ctx) if song_ctx else out.get("selected_song_analysis_context")
    )
    song_name = str(
        (song_ctx or {}).get("title")
        or ctx.get("song")
        or ctx.get("song_source_name")
        or ""
    ).strip()
    song_artist = str((song_ctx or {}).get("artist") or "").strip()
    song_key = str((song_ctx or {}).get("key") or ctx.get("display_key") or "").strip()
    ref_bpm = (song_ctx or {}).get("bpm")
    if ref_bpm in (None, ""):
        ref_bpm = ctx.get("reference_bpm") or ctx.get("practice_bpm")
    meter = str((song_ctx or {}).get("meter") or ctx.get("time_signature") or "").strip()

    inst_line = " + ".join(instruments) if instruments else "ensemble"
    focus_lines = []
    for inst in instruments:
        focs = coerce_focus_list(mapping.get(inst))
        if focs:
            focus_lines.append(f"{inst} → {format_focus_list(focs)}")
        else:
            focus_lines.append(f"{inst} → (no Practice Focus selected)")
    focus_txt = "; ".join(focus_lines) if focus_lines else "selected Practice Focuses"

    ownership = f"Multitrack Mix: {inst_line}. Practice Focuses: {focus_txt}."
    if song_name:
        song_line = f"Selected song: {song_name}"
        if song_artist:
            song_line += f" — {song_artist}"
        if song_key:
            song_line += f". Concert Key: {song_key}"
        if meter:
            song_line += f". Meter: {meter}"
        if ref_bpm not in (None, ""):
            try:
                song_line += f". Reference tempo: {int(float(ref_bpm))} BPM"
            except (TypeError, ValueError):
                song_line += f". Reference tempo: {ref_bpm}"
        song_line += "."
        ownership = f"{ownership} {song_line}"
    if not isolated:
        ownership += (
            " Input: one mixed ensemble file — ensemble-first analysis with limited "
            "per-instrument attribution (no isolated stems)."
        )
    else:
        ownership += (
            " Input: multiple labeled stems — stronger per-instrument evidence is available "
            "alongside ensemble comparison."
        )

    summary = str(out.get("coach_summary") or "").strip()
    summary = re.sub(
        r"(?i)\s*You asked me to evaluate Practice Focuses:[^.]*\.\s*",
        " ",
        summary,
    )
    summary = re.sub(r"(?i)\s*Song context:[^.]*\.\s*", " ", summary).strip()
    if not isolated:
        summary = re.sub(
            r"(?i)Biggest growth edge:\s*pitch[^.]*\.\s*",
            " ",
            summary,
        ).strip()
    if ownership.lower() not in summary.lower():
        out["coach_summary"] = f"{ownership} {summary}".strip()
    else:
        out["coach_summary"] = summary

    ens_lead = (
        "Ensemble findings prioritize timing cohesion, groove, balance, interaction/space, "
        "and musical shape."
    )
    if "ensemble findings prioritize" not in out["coach_summary"].lower():
        out["coach_summary"] = f"{out['coach_summary']} {ens_lead}".strip()
    if out.get("biggest_issue") and "biggest growth edge" not in out["coach_summary"].lower():
        issue = str(out["biggest_issue"])
        if issue.lower().startswith("no single instrument-specific weakness"):
            out["coach_summary"] = f"{out['coach_summary']} {issue}".strip()
        else:
            out["coach_summary"] = (
                f"{out['coach_summary']} Biggest growth edge: {issue}"
            ).strip()

    return out



def run_multitrack_upload_analysis(
    tracks: list[dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Orchestrate Layer vs Mix analysis with visible error payloads.

    Always returns a dict that includes ``multitrack: True`` so the Upload UI can
    render Step 3 success *or* failure instead of silently ignoring the result.
    """
    from recording_analysis import analyze_multitrack, analyze_recording

    ctx = dict(ctx or {})
    rtype = str(ctx.get("recording_type") or RECORDING_TYPE_MT_MIX)
    instruments = [str(x).strip() for x in (ctx.get("instruments") or []) if str(x).strip()]
    target = resolve_multitrack_target_layer(ctx)
    ctx["target_layer"] = target
    ctx["instruments"] = instruments
    ctx["instrument_focuses"] = prune_instrument_focuses_to_project(
        ctx.get("instrument_focuses"),
        instruments,
    )
    if target and instruments and target not in instruments:
        target = instruments[0]
        ctx["target_layer"] = target

    tracks = assign_instruments_to_tracks(
        list(tracks or []),
        instruments=instruments,
        target_layer=target,
        recording_type=rtype,
    )
    err = validate_multitrack_analyze_request(
        recording_type=rtype,
        file_count=len(tracks),
        instruments=instruments,
        target_layer=target,
    )
    if err:
        return {
            "ok": False,
            "multitrack": True,
            "message": err,
            "recording_type": rtype,
            "workflow": ctx.get("workflow"),
            "instruments": instruments,
            "target_layer": target,
            "instrument_focuses": dict(ctx.get("instrument_focuses") or {}),
            "practice_focuses": list(ctx.get("practice_focuses") or []),
        }

    try:
        from upload_media import prepare_multitrack_track_payload

        prepared_tracks: list[dict[str, Any]] = []
        for track in tracks:
            prepared_tracks.append(
                prepare_multitrack_track_payload(
                    track.get("bytes") or b"",
                    str(track.get("filename") or track.get("name") or "upload.wav"),
                    instrument=str(track.get("instrument") or ""),
                )
            )
        tracks = prepared_tracks

        if is_multitrack_layer_type(rtype):
            # Layer contract: one target-layer take is enough.
            primary = tracks[0]
            layer_ctx = dict(ctx)
            layer_ctx["instrument"] = target or primary.get("instrument") or layer_ctx.get("instrument")
            layer_ctx["uploaded_track_count"] = len(tracks)
            layer_ctx["comparison_stem_count"] = len(tracks)
            if target and isinstance(ctx.get("instrument_focuses"), dict):
                focuses = list((ctx.get("instrument_focuses") or {}).get(target) or [])
                if focuses:
                    layer_ctx["practice_focuses"] = focuses
                    layer_ctx["focuses"] = focuses
                    layer_ctx["focus"] = focuses[0]
            result = analyze_recording(
                primary.get("bytes"),
                str(primary.get("filename") or primary.get("name") or "layer.wav"),
                layer_ctx,
            )
            result = enrich_layer_analysis_result(
                dict(result or {}),
                layer_ctx,
                uploaded_track_count=len(tracks),
            )
            result["recording_type"] = rtype
            result["workflow"] = ctx.get("workflow")
            if result.get("ok") and not result.get("coach_summary"):
                result["coach_summary"] = (
                    f"Multitrack Layer analysis for {target or 'selected part'}."
                )
            return result

        # Mix: one file → ensemble-context single take; 2+ → stem comparison.
        if len(tracks) == 1:
            primary = tracks[0]
            mix_ctx = dict(ctx)
            mix_ctx["recording_type"] = rtype or RECORDING_TYPE_MT_MIX
            mix_ctx["multitrack_mode"] = "mix_single"
            mix_ctx["uploaded_track_count"] = 1
            result = analyze_recording(
                primary.get("bytes"),
                str(primary.get("filename") or primary.get("name") or "mix.wav"),
                mix_ctx,
            )
            result = enrich_mix_analysis_result(
                dict(result or {}),
                mix_ctx,
                uploaded_track_count=1,
            )
            result["workflow"] = ctx.get("workflow")
            return result

        mix_ctx = dict(ctx)
        mix_ctx["recording_type"] = rtype or RECORDING_TYPE_MT_MIX
        mix_ctx["multitrack_mode"] = "mix_stems"
        mix_ctx["uploaded_track_count"] = len(tracks)
        mix_ctx["has_isolated_stems"] = True
        result = analyze_multitrack(tracks, mix_ctx)
        result = enrich_mix_analysis_result(
            dict(result or {}),
            mix_ctx,
            uploaded_track_count=len(tracks),
            stem_comparisons=list((result or {}).get("stem_comparisons") or []),
        )
        result["workflow"] = ctx.get("workflow")
        result["reference_bpm"] = ctx.get("reference_bpm") or ctx.get("practice_bpm")
        result["display_key"] = ctx.get("display_key")
        result["song_source_name"] = ctx.get("song") or ctx.get("song_source_name")
        result["song_source_type"] = ctx.get("song_source_type")
        return result
    except Exception as exc:
        return {
            "ok": False,
            "multitrack": True,
            "message": f"Multitrack analysis failed: {exc}",
            "recording_type": rtype,
            "workflow": ctx.get("workflow"),
            "instruments": instruments,
            "target_layer": target,
            "instrument_focuses": dict(ctx.get("instrument_focuses") or {}),
            "practice_focuses": list(ctx.get("practice_focuses") or []),
        }
