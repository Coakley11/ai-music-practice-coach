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
    """Map a Practice Focus to an existing performance score when the signal is real."""
    scores = dict(scores or {})
    key = " ".join(str(focus or "").strip().lower().replace("/", " ").split())
    if not key:
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
    elif "dynamic" in key:
        val = scores.get("musicality")
    elif "pitch" in key or "intonation" in key:
        val = scores.get("pitch")
    else:
        return None
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def build_layer_arrangement_context(
    ctx: dict[str, Any] | None,
    *,
    heard_instruments: list[str] | None = None,
) -> str:
    """Describe non-target project instruments as arrangement context only."""
    ctx = dict(ctx or {})
    target = resolve_multitrack_target_layer(ctx)
    mapping = normalize_instrument_focuses_map(ctx.get("instrument_focuses"))
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
    return (
        f"Arrangement context: {roles}. Evaluate the {target or 'target'} layer for how "
        f"clearly its entrances, phrasing, and rhythmic placement leave room for that role. "
        f"No audio was scored for those other project instruments."
    )


def build_target_layer_focus_analysis(
    *,
    features: Any = None,
    scores: dict[str, Any] | None = None,
    categories: dict[str, Any] | None = None,
    ctx: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Explicit per-Focus coaching blocks for the Layer being analyzed.

    Every selected target Practice Focus gets its own section. Non-target instrument
    Focuses are never scored here (they belong in arrangement context only).
    """
    ctx = dict(ctx or {})
    target = resolve_multitrack_target_layer(ctx)
    mapping = normalize_instrument_focuses_map(ctx.get("instrument_focuses"))
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
    target = resolve_multitrack_target_layer(ctx)
    mapping = normalize_instrument_focuses_map(ctx.get("instrument_focuses"))
    target_focuses = coerce_focus_list(mapping.get(target) if target else None)
    if not target_focuses:
        target_focuses = coerce_focus_list(
            out.get("practice_focuses")
            or ctx.get("practice_focuses")
            or ctx.get("focuses")
        )

    out["multitrack"] = True
    out["multitrack_mode"] = "layer"
    out["target_layer"] = target
    out["instruments"] = list(ctx.get("instruments") or out.get("instruments") or [])
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
        )
        out["target_layer_focus_analysis"] = blocks
        arrangement = build_layer_arrangement_context(ctx, heard_instruments=[target] if target else [])
        out["layer_arrangement_context"] = arrangement

        # Prefixed summary ownership — analyzed target, not every project instrument.
        focus_txt = format_focus_list(target_focuses) if target_focuses else "selected Practice Focuses"
        ownership = (
            f"Multitrack Layer — analyzing {target or 'the uploaded part'} only "
            f"(Practice Focuses: {focus_txt})."
        )
        summary = str(out.get("coach_summary") or "").strip()
        if ownership.lower() not in summary.lower():
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
