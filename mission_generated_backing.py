"""Mission recording: the generated backing is an authoritative asset, not a transport.

"Generate Backing" renders the exact accompaniment for the current Mission context (span or
chord, tempo, meter, passes, count-in, Practice Key, style) and seals its identity. Record then
plays *that* asset in sync with the microphone (see ``mission_recorder``), and the take carries
the asset's identity so Performance + Backing and AI Coaching use the very same backing.

Any change to what the backing would be (tempo, passes, span, key, style, count-in, volume…)
makes the generated backing stale: Record waits until it is generated again.
"""

from __future__ import annotations

import hashlib
from typing import Any

GENERATED_KEY = "_mission_generated_backing"
ASSETS_KEY = "_mission_backing_assets"
_ASSETS_MAX = 4


def backing_fp(wav: bytes) -> str:
    return hashlib.sha256(bytes(wav)).hexdigest()[:16]


def _signature_text(session: dict[str, Any]) -> str:
    from mission_exact_chord_backing import exact_chord_backing_signature

    return repr(exact_chord_backing_signature(session))


def store_asset(session: dict[str, Any], wav: bytes) -> str:
    fp = backing_fp(wav)
    assets = session.get(ASSETS_KEY)
    assets = dict(assets) if isinstance(assets, dict) else {}
    assets.pop(fp, None)
    assets[fp] = bytes(wav)
    while len(assets) > _ASSETS_MAX:
        assets.pop(next(iter(assets)))
    session[ASSETS_KEY] = assets
    return fp


def backing_asset(session: dict[str, Any], fp: str) -> bytes | None:
    assets = session.get(ASSETS_KEY)
    if isinstance(assets, dict) and fp and isinstance(assets.get(fp), (bytes, bytearray)):
        return bytes(assets[fp])
    return None


def generate_mission_backing(session: dict[str, Any]) -> dict[str, Any] | None:
    """Render the exact backing for the current Mission context and seal its identity."""
    from mission_exact_chord_backing import generate_exact_chord_backing_wav, invalidate_exact_chord_backing_cache
    from mission_live_recording_mix import wav_duration_sec
    from mission_practice_context import (
        MISSION_BACKING_SOUNDING_SPAN_KEY,
        MISSION_EXACT_BACKING_ARMED_KEY,
        ensure_mission_practice_context,
    )
    from songs.meter import meter_timing

    invalidate_exact_chord_backing_cache(session)
    wav, label = generate_exact_chord_backing_wav(session)
    if not wav:
        return None
    ctx = ensure_mission_practice_context(session)
    fp = store_asset(session, wav)
    span = ctx.span if ctx is not None else None
    bpm = int((span or {}).get("bpm") or (ctx.tempo_bpm if ctx else 100))
    meter = str((span or {}).get("meter") or (ctx.meter if ctx else "4/4"))
    count_in_bars = int(ctx.count_in_bars if ctx else 0)
    claim = session.get(MISSION_BACKING_SOUNDING_SPAN_KEY) if span else None
    rec = {
        "fp": fp,
        "signature": _signature_text(session),
        "label": str(label or ""),
        "bpm": bpm,
        "meter": meter,
        "loops": int(ctx.loops if ctx and ctx.loop else 1),
        "count_in_bars": count_in_bars,
        "count_in_sec": round(count_in_bars * meter_timing(bpm, meter).bar_sec, 4),
        "duration_sec": round(wav_duration_sec(wav), 3),
        "kind": "span" if span else "chord",
        "span_id": str((span or {}).get("span_id") or ""),
        "span_fingerprint": str((span or {}).get("span_fingerprint") or ""),
        "timeline": [str(t.get("chord") or "") for t in (span or {}).get("timeline") or []],
        "chord": str(ctx.chord.symbol if ctx and not span else ""),
        "practice_key": str((span or {}).get("practice_key") or (ctx.display_key if ctx else "")),
        "arrangement": dict((claim or {}).get("arrangement") or {}),
    }
    session[GENERATED_KEY] = rec
    session[MISSION_EXACT_BACKING_ARMED_KEY] = True
    return rec


def current_generated_backing(session: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """(generated backing, stale reason). Reason "" = ready to record with."""
    rec = session.get(GENERATED_KEY)
    if not isinstance(rec, dict) or not rec.get("fp"):
        return None, "none"
    if backing_asset(session, str(rec["fp"])) is None:
        return rec, "missing"
    if not session.get("mission_exact_backing_wav"):
        return rec, "settings changed"  # a context change invalidated the rendered backing
    try:
        if _signature_text(session) != str(rec.get("signature") or ""):
            return rec, "settings changed"
    except Exception:
        return rec, "settings changed"
    return rec, ""


def clear_generated_backing(session: dict[str, Any]) -> None:
    session.pop(GENERATED_KEY, None)


__all__ = [
    "ASSETS_KEY",
    "GENERATED_KEY",
    "backing_asset",
    "backing_fp",
    "clear_generated_backing",
    "current_generated_backing",
    "generate_mission_backing",
    "store_asset",
]
