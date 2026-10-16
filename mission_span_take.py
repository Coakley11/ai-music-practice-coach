"""MC4 — the span take being analyzed: its sealed span, its alignment and its result.

One record per take, keyed by the audio fingerprint, so:

* a live take recorded on Missions keeps the span it was recorded against (and the app's own
  alignment — bar 1 follows the count-in, the same model the backing mix uses);
* an uploaded file gets a detected alignment the player can nudge / confirm; that choice is
  stored per file, so it survives reruns and refresh and never leaks to another file;
* the expensive transcription runs once per file; nudges only re-assign notes;
* nothing here is reused for another song: a take staged for song A is ignored on song B.

Single-chord takes never create or read any of this.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

SPAN_TAKE_KEY = "_mission_span_take"
SPAN_ALIGNMENTS_KEY = "_mission_span_alignments"
SPAN_RESULT_CACHE_KEY = "_mission_span_take_result"
CURRENT_AUDIO_FP_KEY = "_analysis_current_audio_fp"


def audio_fp(audio: bytes) -> str:
    from mission_span_transcription import audio_fingerprint

    return audio_fingerprint(audio)


def _song_session(session: dict[str, Any]) -> str:
    from mission_span_recording_context import _song_session as song_session

    return song_session(session)


# --------------------------------------------------------------------------- record / clear


def record_span_take(
    session: dict[str, Any], *, audio_bytes: bytes, source: str, span: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Seal the span a take was made for (called from the Missions → Upload handoff)."""
    from mission_span_recording_alignment import live_alignment

    if span is None:
        from mission_practice_context import ensure_mission_practice_context
        from mission_span_recording_context import span_scope_active

        if not span_scope_active(session):
            session.pop(SPAN_TAKE_KEY, None)  # one-chord take: nothing else is touched
            return None
        ctx = ensure_mission_practice_context(session, force=True)
        span = ctx.span if ctx is not None else None
    if not span:
        clear_span_take(session)
        return None
    fp = audio_fp(audio_bytes)
    take: dict[str, Any] = {
        "version": 1,
        "span": copy.deepcopy(span),
        "source": str(source or "live"),
        "audio_fp": fp,
        "song_session": str(span.get("song_session") or _song_session(session)),
    }
    if take["source"] == "live":
        # The backing this take was played against (arrangement + transport), so the
        # Performance + Backing preview is identifiable as that exact accompaniment.
        try:
            from mission_practice_context import MISSION_BACKING_SOUNDING_SPAN_KEY

            claim = session.get(MISSION_BACKING_SOUNDING_SPAN_KEY)
            if isinstance(claim, dict) and session.get("mission_exact_backing_wav"):
                take["backing"] = copy.deepcopy(claim)
        except ImportError:
            pass
        al = live_alignment(
            count_in_sec=float(span.get("count_in_sec") or 0.0),
            loop_sec=float(span.get("loop_sec") or 0.0),
            loops=int(span.get("loops") or 1),
        )
        take["alignment"] = al.to_dict()
        set_alignment(session, fp, al)
    session[SPAN_TAKE_KEY] = take
    return take


def clear_span_take(session: dict[str, Any]) -> None:
    session.pop(SPAN_TAKE_KEY, None)
    session.pop(SPAN_RESULT_CACHE_KEY, None)


def set_current_audio(session: dict[str, Any], audio_bytes: bytes | None) -> str:
    fp = audio_fp(audio_bytes) if audio_bytes else ""
    session[CURRENT_AUDIO_FP_KEY] = fp
    return fp


# --------------------------------------------------------------------------- resolve


def _live_span_for_upload(session: dict[str, Any]) -> dict[str, Any] | None:
    """A file uploaded on Upload Analysis as a Mission Recording while a span Mission is set up."""
    try:
        from recording_analysis_context import is_mission_recording_type
    except ImportError:  # pragma: no cover
        return None
    if not is_mission_recording_type(session.get("analysis_recording_type")):
        return None
    from mission_practice_context import ensure_mission_practice_context

    ctx = ensure_mission_practice_context(session)
    return copy.deepcopy(ctx.span) if ctx is not None and ctx.span else None


def analysis_span_take(session: dict[str, Any], audio_fp_value: str | None = None) -> dict[str, Any] | None:
    """The span take for the audio being analyzed now (``None`` → single-chord / ordinary take)."""
    fp = str(audio_fp_value if audio_fp_value is not None else session.get(CURRENT_AUDIO_FP_KEY) or "")
    take = session.get(SPAN_TAKE_KEY)
    if isinstance(take, dict) and take.get("span"):
        staged_for = str(take.get("song_session") or "")
        if staged_for and staged_for != _song_session(session):
            return None  # Song A's take never analyzes Song B's upload
        if not fp or take.get("audio_fp") == fp:
            return take
    span = _live_span_for_upload(session)
    if span is None:
        return None
    return {"version": 1, "span": span, "source": "upload", "audio_fp": fp, "song_session": span.get("song_session")}


# --------------------------------------------------------------------------- alignment


def _alignment_key(fp: str, span: dict[str, Any]) -> str:
    return f"{fp}|{span.get('span_fingerprint') or ''}"


def get_alignment(session: dict[str, Any], fp: str, span: dict[str, Any]):
    from mission_span_recording_alignment import Alignment

    store = session.get(SPAN_ALIGNMENTS_KEY)
    if not isinstance(store, dict):
        return None
    return Alignment.from_dict(store.get(_alignment_key(fp, span)) or store.get(fp))


def set_alignment(session: dict[str, Any], fp: str, alignment: Any, span: dict[str, Any] | None = None) -> None:
    store = session.get(SPAN_ALIGNMENTS_KEY)
    store = dict(store) if isinstance(store, dict) else {}
    key = _alignment_key(fp, span) if span else fp
    store[key] = alignment.to_dict()
    if len(store) > 12:
        for k in list(store)[: len(store) - 12]:
            store.pop(k, None)
    session[SPAN_ALIGNMENTS_KEY] = store
    session.pop(SPAN_RESULT_CACHE_KEY, None)


def chord_pcs(span: dict[str, Any]) -> list[tuple[int, ...]]:
    from melodic_pattern_engine import build_context

    key = str(span.get("practice_key") or "C")
    return [tuple(build_context(key, str(t.get("chord") or "")).chord_pcs) for t in span.get("timeline") or []]


def resolve_alignment(session: dict[str, Any], take: dict[str, Any], transcription: dict[str, Any]):
    """Stored alignment for this file (live / confirmed / adjusted), else a fresh detection."""
    from mission_span_recording_alignment import build_grid, estimate_upload_alignment

    span = take["span"]
    fp = str(take.get("audio_fp") or transcription.get("fingerprint") or "")
    stored = get_alignment(session, fp, span)
    if stored is not None:
        return stored
    if take.get("source") == "live" and take.get("alignment"):
        from mission_span_recording_alignment import Alignment

        al = Alignment.from_dict(take["alignment"])
        if al is not None:
            return al
    grid = build_grid(span["timeline"], bpm=int(span.get("bpm") or 100), meter=str(span.get("meter") or "4/4"))
    al = estimate_upload_alignment(transcription, grid, chord_pcs=chord_pcs(span))
    set_alignment(session, fp, al, span)
    return al


# --------------------------------------------------------------------------- analysis


def run_span_take_analysis(
    session: dict[str, Any], take: dict[str, Any], audio_bytes: bytes, filename: str = "take.wav",
) -> dict[str, Any]:
    """Transcribe (once per file), align, evaluate; cached until the alignment changes."""
    from mission_span_take_evaluation import evaluate_span_take
    from mission_span_transcription import session_transcription

    transcription = session_transcription(session, audio_bytes, filename)
    take = dict(take)
    take["audio_fp"] = take.get("audio_fp") or transcription.get("fingerprint")
    alignment = resolve_alignment(session, take, transcription)
    span = take["span"]
    key = hashlib.sha256(
        json.dumps([take["audio_fp"], span.get("span_fingerprint"), span.get("mission_id"), alignment.to_dict()],
                   sort_keys=True, default=str).encode()
    ).hexdigest()[:20]
    cached = session.get(SPAN_RESULT_CACHE_KEY)
    if isinstance(cached, dict) and cached.get("key") == key:
        return cached["result"]
    result = evaluate_span_take(span, transcription, alignment, level=str(span.get("level") or ""),
                                mission_id=str(span.get("mission_id") or ""))
    result["take_source"] = str(take.get("source") or "")
    result["instrument"] = str(span.get("instrument") or "")
    result["song_title"] = str(span.get("song_title") or "")
    result["section"] = str(span.get("section") or "")
    result["duration_sec"] = transcription.get("duration")
    session[SPAN_RESULT_CACHE_KEY] = {"key": key, "result": result}
    return result


# --------------------------------------------------------------------------- snapshot / Practice Log


def span_snapshot_fields(span: dict[str, Any]) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    """(Mission label, Mission id, mission_parameters, durable span summary) for a span take.

    Durable: readable later without re-resolving anything from the then-current song.
    """
    from mission_span_recording_context import span_chart_label

    label = str(span.get("mission_label") or "")
    mid = str(span.get("mission_id") or "")
    timeline = [
        {"chord": str(t.get("chord") or ""), "chart_chord": str(t.get("chart_chord") or t.get("chord") or ""),
         "bars": int(t.get("bars") or 1), "start_bar": int(t.get("start_bar") or 0)}
        for t in span.get("timeline") or []
    ]
    params = {
        "mission_type": label,
        "mission_id": mid,
        "scope": str(span.get("scope") or ""),
        "span_label": span_chart_label(span),
        "span_chords": [t["chord"] for t in timeline],
        "section": str(span.get("section") or ""),
        "practice_key": str(span.get("practice_key") or ""),
        "tempo_bpm": int(span.get("bpm") or 0),
        "meter": str(span.get("meter") or ""),
        "loop_bars": int(span.get("loop_bars") or 0),
        "evaluation_focus": str(span.get("evaluation_focus") or ""),
        "backing_track": True,
    }
    durable = {
        "mission_label": label,
        "mission_id": mid,
        "song_title": str(span.get("song_title") or ""),
        "span_label": params["span_label"],
        "relationship": str(span.get("relationship_label") or ""),
        "section": params["section"],
        "practice_key": params["practice_key"],
        "chart_key": str(span.get("chart_key") or ""),
        "instrument": str(span.get("instrument") or ""),
        "bpm": params["tempo_bpm"],
        "meter": params["meter"],
        "loop_bars": params["loop_bars"],
        "timeline": timeline,
        "level": str(span.get("level") or ""),
    }
    return label, mid, params, durable


# --------------------------------------------------------------------------- persistence


def span_take_for_envelope(session: dict[str, Any], fp: str) -> dict[str, Any] | None:
    take = session.get(SPAN_TAKE_KEY)
    if not (isinstance(take, dict) and take.get("span") and take.get("audio_fp") == fp):
        return None
    out = copy.deepcopy(take)
    al = get_alignment(session, fp, take["span"])
    if al is not None:
        out["alignment"] = al.to_dict()
    return out


def sync_alignment_to_envelope(session: dict[str, Any], fp: str) -> bool:
    """Write the player's current alignment for ``fp`` into the pending-upload envelope.

    The envelope is what a refresh restores, so a confirmed / adjusted start must live there
    too (session copy and the canonical Creative workspace blob that autosave persists).
    """
    try:
        from mission_pending_upload_analysis import PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY
    except ImportError:  # pragma: no cover
        return False
    take = session.get(SPAN_TAKE_KEY)
    if not (isinstance(take, dict) and take.get("span") and take.get("audio_fp") == fp):
        return False
    al = get_alignment(session, fp, take["span"])
    if al is None:
        return False
    take = dict(take)
    take["alignment"] = al.to_dict()
    session[SPAN_TAKE_KEY] = take
    changed = False
    env = session.get(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY)
    if isinstance(env, dict) and isinstance(env.get("span_take"), dict) and env["span_take"].get("audio_fp") == fp:
        env = copy.deepcopy(env)
        env["span_take"]["alignment"] = al.to_dict()
        session[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY] = env
        changed = True
    cws = session.get("creative_workspace_state")
    blob_env = cws.get(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY) if isinstance(cws, dict) else None
    if isinstance(blob_env, dict) and isinstance(blob_env.get("span_take"), dict) and blob_env["span_take"].get("audio_fp") == fp:
        blob = copy.deepcopy(cws)
        blob[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY]["span_take"]["alignment"] = al.to_dict()
        try:
            from creative_workspace_state_persistence import write_canonical_creative_workspace

            write_canonical_creative_workspace(session, blob, reason="mission_span_alignment")
        except ImportError:  # pragma: no cover
            session["creative_workspace_state"] = blob
        changed = True
    return changed


def restore_span_take_from_envelope(session: dict[str, Any], env: dict[str, Any]) -> bool:
    """Envelope v2 → session (a v1 envelope / missing block means a one-chord take)."""
    block = env.get("span_take") if isinstance(env, dict) else None
    if not (isinstance(block, dict) and block.get("span") and block.get("audio_fp")):
        clear_span_take(session)
        return False
    session[SPAN_TAKE_KEY] = copy.deepcopy(block)
    al_raw = block.get("alignment")
    if isinstance(al_raw, dict):
        from mission_span_recording_alignment import Alignment

        al = Alignment.from_dict(al_raw)
        if al is not None:
            set_alignment(session, str(block["audio_fp"]), al, block["span"])
    return True


__all__ = [
    "CURRENT_AUDIO_FP_KEY",
    "SPAN_TAKE_KEY",
    "analysis_span_take",
    "chord_pcs",
    "clear_span_take",
    "get_alignment",
    "record_span_take",
    "resolve_alignment",
    "restore_span_take_from_envelope",
    "run_span_take_analysis",
    "set_alignment",
    "set_current_audio",
    "span_take_for_envelope",
    "sync_alignment_to_envelope",
]
