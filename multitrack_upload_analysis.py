"""Multitrack Upload Analysis — input contracts + orchestration (Layer vs Mix)."""

from __future__ import annotations

from typing import Any

from recording_analysis_context import RECORDING_TYPE_MT_LAYER, RECORDING_TYPE_MT_MIX


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
            result = dict(result or {})
            result["multitrack"] = True
            result["recording_type"] = rtype
            result["workflow"] = ctx.get("workflow")
            result["target_layer"] = target
            result["instruments"] = instruments
            result["instrument_focuses"] = dict(ctx.get("instrument_focuses") or {})
            if not result.get("practice_focuses"):
                result["practice_focuses"] = list(layer_ctx.get("practice_focuses") or [])
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
            if result.get("ok"):
                result["coach_summary"] = (
                    str(result.get("coach_summary") or "")
                    + (
                        " Multitrack Mix: treating this upload as the ensemble blend while "
                        "preserving per-instrument Practice Focus mappings."
                    )
                ).strip()
            return result

        result = analyze_multitrack(tracks, ctx)
        result = dict(result or {})
        result["multitrack"] = True
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
