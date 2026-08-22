"""Multitrack Upload Analysis — input contracts + orchestration (Layer vs Mix)."""

from __future__ import annotations

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
    """
    scores = dict(scores or {})
    key = " ".join(str(focus or "").strip().lower().replace("/", " ").split())
    if not key:
        return None
    if "dynamic" in key:
        return None
    if "articulation" in key or key in {"technique", "tonguing", "attack"}:
        val = scores.get("technique")
    elif key == "tone" or "tone color" in key or "timbre" in key:
        val = scores.get("tone")
    elif "phras" in key or "musicality" in key or "expression" in key:
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
                form_bit = f" around {', '.join(names[:3])} transitions"
    song_bit = ""
    if song_name:
        song_bit = f" in {song_name}" + (f" ({song_key})" if song_key else "")
    return (
        f"Arrangement context: {roles}. Evaluate the {target or 'target'} layer{song_bit} for "
        f"how clearly its entrances, phrasing, and rhythmic placement leave room for that role"
        f"{form_bit}. No audio was scored for those other project instruments."
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
                f"Selected song harmonic context: {song_name} in {song_key}."
            )
        elif song_key:
            findings.append(f"Selected song key for Scales coaching: {song_key}.")
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
                f"Chord-tone hit rate vs selected-song chords ≈ {float(chord_tone):.0f}%."
            )
        if guide_tone is not None:
            findings.append(
                f"Guide-tone (3rds/7ths) usage vs selected-song harmony ≈ {float(guide_tone):.0f}%."
            )
        if scale_adh is None and chord_tone is None:
            findings.append(
                "Pitch-class harmonic fit was limited in this take — coach from the selected "
                "song key/chords on the next loop."
            )

        if mapped is not None and mapped >= 70:
            went_well = (
                f"{target or 'This layer'} shows strong tonal alignment with "
                f"{song_name or 'the selected song'}'s scale/harmony."
            )
            improve_to = (
                "Tighten weaker chords in the progression — land chord tones on strong beats, "
                "especially 3rds and 7ths through ii–V motion."
            )
        elif mapped is not None and mapped >= 50:
            went_well = (
                f"{target or 'This layer'} has usable scale material inside "
                f"{song_name or 'the selected song'}, with room to fit local chords more tightly."
            )
            improve_to = (
                f"Over the next take, outline chord tones of "
                f"{' → '.join(chords[:3]) if chords else song_key} before freer scale runs."
            )
        else:
            went_well = (
                f"{target or 'This layer'} establishes pitch material to reshape toward "
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
            drill = (
                f"Play {' → '.join(chords[:4])} slowly — hold the 3rd and 7th of each chord "
                f"for two beats before connecting with {song_key or 'the song'} scale tones."
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
            f"{target or 'This layer'} provides pitch material for scale practice."
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
                    f"{target or 'This layer'} shows clear, intentional attacks with useful "
                    "contrast between notes."
                )
            elif onset_strength >= 0.8:
                went_well = (
                    f"{target or 'This layer'} produces audible attacks — a usable articulation "
                    "foundation is present."
                )
            else:
                went_well = (
                    f"{target or 'This layer'} has a starting articulation profile, but attacks "
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
                if text and text not in findings:
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
                    f"{target or 'This layer'} keeps a relatively consistent tone color through "
                    "the take."
                )
            else:
                went_well = (
                    f"{target or 'This layer'} establishes a recognizable tone center to refine."
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
                    f"{target or 'This layer'} shows usable dynamic contrast between softer and "
                    "louder regions."
                )
                improve_to = (
                    "Increase intentional contrast between phrase peaks and releases — plan "
                    "pp/mf/f shapes rather than accidental spikes."
                )
            elif dyn_range > 0:
                went_well = (
                    f"{target or 'This layer'} has some amplitude variation to shape more deliberately."
                )
                improve_to = (
                    "Widen intentional dynamic contrast: softer approaches, fuller phrase peaks, "
                    "and controlled releases."
                )
            else:
                went_well = (
                    f"{target or 'This layer'} holds a steady energy level — a clean base for "
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
            findings.extend(str(x) for x in (musicality_cat.get("findings") or [])[:3])
            went_well = (
                f"{target or 'This layer'} shows phrase shape you can build on."
                if (mapped or 0) >= 65
                else f"{target or 'This layer'} has phrase material — contour can be clearer."
            )
            improve_to = (
                "Shape longer arcs: breathe/plan destinations, leave space, and vary density."
            )
            drill = (
                f"{target or 'Layer'} phrasing drill: 4-bar idea → leave 2 beats rest → answer "
                "with a related shape."
            )
            assessment = (
                f"{mapped}/100 (musicality proxy)"
                if mapped is not None
                else "Qualitative phrasing read"
            )
        elif "timing" in fl or "rhythm" in fl or "groove" in fl:
            findings.extend(str(x) for x in (timing_cat.get("findings") or [])[:3])
            if groove:
                findings.append(f"Groove tightness estimate ≈ {groove * 100:.0f}%.")
            went_well = (
                f"{target or 'This layer'} locks usefully with the pulse."
                if (mapped or 0) >= 65
                else f"{target or 'This layer'} has a rhythmic outline to tighten."
            )
            improve_to = (
                "Place entrances and releases more deliberately against the grid or click."
            )
            drill = (
                f"{target or 'Layer'} rhythm drill: entrances on beat 1 only for 8 bars, then "
                "restore the phrase against a click."
            )
            assessment = (
                f"{mapped}/100 (timing/groove proxy)"
                if mapped is not None
                else "Qualitative rhythm/timing read"
            )
        else:
            # Generic Focus: still explicit, without inventing unsupported scores.
            went_well = (
                f"{target or 'This layer'} was analyzed with {focus} as an explicit coaching goal."
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
            # Pull a related category tip when available.
            for cat in (tech_cat, tone_cat, timing_cat, musicality_cat):
                for tip in (cat.get("tips") or [])[:1]:
                    text = str(tip).strip()
                    if text:
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
            result = analyze_recording(
                primary.get("bytes"),
                str(primary.get("filename") or primary.get("name") or "mix.wav"),
                mix_ctx,
            )
            result = dict(result or {})
            result["multitrack"] = True
            result["recording_type"] = rtype or RECORDING_TYPE_MT_MIX
            result["workflow"] = ctx.get("workflow")
            result["instruments"] = instruments
            result["instrument_focuses"] = dict(ctx.get("instrument_focuses") or {})
            result["practice_focuses"] = list(ctx.get("practice_focuses") or [])
            result["multitrack_mode"] = "mix_single"
            result["uploaded_track_count"] = 1
            if result.get("ok"):
                result["coach_summary"] = (
                    str(result.get("coach_summary") or "")
                    + (
                        " Multitrack Mix: treating this upload as the ensemble blend. "
                        "Per-instrument Practice Focus mappings guide arrangement intent; "
                        "this single mix file is coached at ensemble level (balance, timing "
                        "cohesion, groove, interaction) rather than as separately scored stems."
                    )
                ).strip()
            return result

        result = analyze_multitrack(tracks, ctx)
        result = dict(result or {})
        result["multitrack"] = True
        result["multitrack_mode"] = "mix_stems"
        result["uploaded_track_count"] = len(tracks)
        result.setdefault("recording_type", rtype)
        result.setdefault("instruments", instruments)
        result.setdefault("instrument_focuses", dict(ctx.get("instrument_focuses") or {}))
        result.setdefault("practice_focuses", list(ctx.get("practice_focuses") or []))
        if isinstance(ctx.get("selected_song_analysis_context"), dict):
            result["selected_song_analysis_context"] = dict(ctx["selected_song_analysis_context"])
            song_name = str(ctx["selected_song_analysis_context"].get("title") or "").strip()
            if song_name and result.get("ok"):
                summary = str(result.get("coach_summary") or "")
                if song_name.lower() not in summary.lower():
                    result["coach_summary"] = (
                        f"Song context: {song_name}. {summary}"
                    ).strip()
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
