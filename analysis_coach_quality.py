"""Helpers for context-aware analysis status messages + coaching quality utilities."""

from __future__ import annotations

from typing import Any, Iterable, Sequence


_BASELINE_POOL = ("timing", "pitch", "groove", "tone", "musicality")

_SYNONYM_KEYS: dict[str, str] = {
    "timing": "timing",
    "pulse": "timing",
    "groove": "groove",
    "timing/groove": "timing_groove",
    "timing groove": "timing_groove",
    "pitch": "pitch",
    "intonation": "pitch",
    "pitch / intonation": "pitch",
    "tone": "tone",
    "musicality": "musicality",
    "expression": "musicality",
    "articulation": "articulation",
    "phrasing": "phrasing",
    "phrase structure": "phrase_structure",
    "phrase pacing": "phrase_structure",
    "scale/mode usage": "scale_mode",
    "scale mode usage": "scale_mode",
    "scale adherence": "scale_mode",
    "dynamics": "dynamics",
    "balance": "balance",
    "ensemble": "ensemble",
    "ensemble interaction": "ensemble",
    "comping": "comping",
}


def _focus_token_key(label: str) -> str:
    text = " ".join(str(label or "").strip().lower().replace("/", " ").replace("-", " ").split())
    if text in _SYNONYM_KEYS:
        return _SYNONYM_KEYS[text]
    for key, canon in _SYNONYM_KEYS.items():
        if key in text or text in key:
            return canon
    return text or "item"


def _dedupe_labels(labels: Iterable[str], *, limit: int | None = None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in labels:
        label = str(raw or "").strip()
        if not label:
            continue
        key = _focus_token_key(label)
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
        if limit is not None and len(out) >= limit:
            break
    return out


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _instrument_short(name: str) -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    lower = text.lower()
    mapping = {
        "tenor saxophone": "sax",
        "alto saxophone": "sax",
        "soprano saxophone": "sax",
        "saxophone": "sax",
        "flute": "flute",
        "clarinet": "clarinet",
        "trumpet": "trumpet",
        "piano": "piano",
        "guitar": "guitar",
        "voice": "voice",
        "bass": "bass",
    }
    for key, short in mapping.items():
        if key in lower:
            return short
    return text.split()[0].lower()


def is_mission_evaluation_active(
    *,
    recording_type: Any = None,
    session_state: dict[str, Any] | None = None,
    ctx: dict[str, Any] | None = None,
) -> bool:
    """True only for explicit Mission Recording or genuine Creative Mission handoff.

    Selected Evaluating Criteria / Focuses alone must NOT activate Mission wording.
    Ambient Creative mission state alone must NOT activate Mission wording.

    Ownership rule: when the *current* recording type is an ordinary take
    (Practice / Solo / Backing / etc.), stale session handoff markers and old
    ``mission_evaluation_active`` flags must NOT keep Mission wording alive.
    Those flags are owned by the current recording/context snapshot and must be
    recomputed per take.
    """
    ctx = dict(ctx or {})
    rtype = (
        recording_type
        or ctx.get("recording_type")
        or ctx.get("analysis_recording_type")
        or (session_state or {}).get("analysis_recording_type")
    )
    try:
        from recording_analysis_context import (
            is_genuine_mission_upload_handoff,
            is_mission_recording_type,
        )
    except ImportError:
        text = str(rtype or "").strip().lower().replace("_", " ")
        mission_type = text in {"mission recording", "mission"}
        if rtype and not mission_type:
            return False
        if mission_type:
            return True
        ss = session_state or {}
        return bool(
            ss.get("_mission_upload_analysis_handoff")
            or ctx.get("_mission_upload_analysis_handoff")
            or ctx.get("from_mission_handoff") is True
            or ctx.get("mission_evaluation_active") is True
        )

    # Explicit ordinary recording type wins over stale session/ctx Mission flags.
    if rtype and not is_mission_recording_type(rtype):
        return False

    if is_mission_recording_type(rtype):
        return True
    if ctx.get("mission_evaluation_active") is True:
        return True
    if ctx.get("from_mission_handoff") is True:
        return True
    if session_state is not None and is_genuine_mission_upload_handoff(session_state):
        return True
    # Handoff marker copied onto durable analysis context/result.
    if ctx.get("_mission_upload_analysis_handoff"):
        return True
    return False


def criteria_report_heading(*, mission_evaluation_active: bool) -> str:
    """Report block title — Mission language only when Mission evaluation is active."""
    if mission_evaluation_active:
        return "🎯 AI improvisation evaluation"
    return "Selected Evaluating Criteria"


def criteria_overall_score_label(*, mission_evaluation_active: bool) -> str:
    if mission_evaluation_active:
        return "Overall Improvisation Score"
    return "Overall criteria score"


def build_analysis_status_message(
    ctx: dict[str, Any] | None = None,
    *,
    mission_ids: Sequence[str] | None = None,
    multitrack: bool = False,
    mission_evaluation_active: bool | None = None,
    session_state: dict[str, Any] | None = None,
) -> str:
    """Compose a concise spinner/status line from selected criteria + Focuses + baselines.

    ``mission_ids`` (Evaluating Criteria) may drive analysis content, but they do
    **not** by themselves add \"improvisation missions\" to the status line.
    """
    ctx = dict(ctx or {})
    criteria = _as_str_list(
        ctx.get("evaluating_criteria_labels")
        or ctx.get("mission_labels")
        or []
    )
    # Prefer full Focus lists; fall back to scalar / mapping.
    focuses = _as_str_list(ctx.get("practice_focuses") or ctx.get("focuses") or [])
    if not focuses:
        focuses = _as_str_list(ctx.get("focus") or ctx.get("practice_focus") or "")
    instrument_focuses = ctx.get("instrument_focuses")
    if isinstance(instrument_focuses, dict) and instrument_focuses:
        # Multitrack: prefer per-instrument Focus phrases.
        mt_bits: list[str] = []
        for inst, foc_list in instrument_focuses.items():
            short = _instrument_short(str(inst))
            for foc in _as_str_list(foc_list)[:2]:
                mt_bits.append(f"{short} {foc.lower()}" if short else foc.lower())
        if mt_bits and multitrack:
            focuses = mt_bits

    # Keep mission_ids available for callers/tests, but ignore for Mission wording.
    _ = [str(x).strip() for x in (mission_ids or ctx.get("mission_ids") or []) if str(x).strip()]
    if mission_evaluation_active is None:
        mission_evaluation_active = is_mission_evaluation_active(
            ctx=ctx,
            session_state=session_state,
        )

    parts: list[str] = []
    parts.extend(_dedupe_labels(criteria, limit=3))

    # Focuses that are not already covered by criteria synonyms.
    criteria_keys = {_focus_token_key(c) for c in parts}
    focus_candidates = []
    for foc in focuses:
        if _focus_token_key(foc) in criteria_keys:
            continue
        focus_candidates.append(foc)
    parts.extend(_dedupe_labels(focus_candidates, limit=2))

    if multitrack:
        # Prefer ensemble concepts over generic tone/musicality for Multitrack.
        ensemble_first = ["timing", "groove", "balance", "ensemble interaction"]
        baseline_pick = []
        present = {_focus_token_key(p) for p in parts}
        for area in ensemble_first:
            key = _focus_token_key(area)
            if key in present:
                continue
            baseline_pick.append(area)
            present.add(key)
            if len(baseline_pick) >= 3:
                break
    else:
        present = {_focus_token_key(p) for p in parts}
        baseline_pick = []
        for area in _BASELINE_POOL:
            key = _focus_token_key(area)
            if key in present or (
                key in {"timing", "groove"} and "timing_groove" in present
            ):
                continue
            if "timing_groove" in present and key in {"timing", "groove"}:
                continue
            baseline_pick.append(area)
            present.add(key)
            if len(baseline_pick) >= 3:
                break
    parts.extend(baseline_pick)

    parts = _dedupe_labels(parts)
    if mission_evaluation_active and "improvisation missions" not in {p.lower() for p in parts}:
        parts.append("improvisation missions")

    if not parts:
        parts = ["timing", "pitch", "groove", "musicality"]

    # Grammar: a, b, and c
    if len(parts) == 1:
        body = parts[0]
    elif len(parts) == 2:
        body = f"{parts[0]} and {parts[1]}"
    else:
        body = ", ".join(parts[:-1]) + f", and {parts[-1]}"
    return f"Analyzing {body}…"


def _is_other_or_not_a_song(ctx: dict[str, Any]) -> bool:
    source = str(ctx.get("song_source_type") or "").strip().lower()
    song_ctx = ctx.get("selected_song_analysis_context")
    if isinstance(song_ctx, dict):
        source = source or str(song_ctx.get("source_type") or "").strip().lower()
    return ("other" in source) or ("not a song" in source)


def _collect_song_chords(ctx: dict[str, Any]) -> list[str]:
    """Flatten chord tokens from target_chords, sections, and selected-song context."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(token: object) -> None:
        text = str(token or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)

    for c in ctx.get("target_chords") or []:
        _add(c)
    sections = ctx.get("sections")
    if isinstance(sections, dict):
        for sec_chords in sections.values():
            if isinstance(sec_chords, (list, tuple)):
                for c in sec_chords:
                    _add(c)
    song_ctx = ctx.get("selected_song_analysis_context")
    if isinstance(song_ctx, dict):
        for c in song_ctx.get("chord_progression") or []:
            _add(c)
        nested = song_ctx.get("sections")
        if isinstance(nested, dict):
            for sec_chords in nested.values():
                if isinstance(sec_chords, (list, tuple)):
                    for c in sec_chords:
                        _add(c)
    return out


def _named_song_sections(ctx: dict[str, Any]) -> list[str]:
    """Named form labels (Verse/Chorus/A/B/…) — empty when only a flat progression exists."""
    names: list[str] = []
    seen: set[str] = set()
    for sections in (
        ctx.get("sections"),
        (ctx.get("selected_song_analysis_context") or {}).get("sections")
        if isinstance(ctx.get("selected_song_analysis_context"), dict)
        else None,
    ):
        if not isinstance(sections, dict):
            continue
        for key in sections.keys():
            text = str(key or "").strip()
            if text and text not in seen:
                seen.add(text)
                names.append(text)
    return names


def has_song_harmony_context(ctx: dict[str, Any] | None) -> bool:
    """True when Upload-selected song provides real key and/or chord progression.

    Named Verse/Chorus/A/B form is NOT required. Other / Not a Song is always False.
    """
    ctx = dict(ctx or {})
    if _is_other_or_not_a_song(ctx):
        return False
    song_ctx = ctx.get("selected_song_analysis_context")
    if isinstance(song_ctx, dict) and "has_song_harmony" in song_ctx:
        return bool(song_ctx.get("has_song_harmony"))
    key = str(ctx.get("display_key") or "").strip()
    if isinstance(song_ctx, dict):
        key = key or str(song_ctx.get("key") or "").strip()
    if key:
        return True
    return bool(_collect_song_chords(ctx))


def has_song_form_context(ctx: dict[str, Any] | None) -> bool:
    """True when Upload-selected song has named form sections (Verse/Chorus/A/B/…).

    Key + flat chord progression alone do NOT count as form.
    """
    ctx = dict(ctx or {})
    if _is_other_or_not_a_song(ctx):
        return False
    return bool(_named_song_sections(ctx))


def instrument_family(instrument: str) -> str:
    text = str(instrument or "").strip().lower()
    if not text:
        return "general"
    if "flute" in text:
        return "flute"
    if "clarinet" in text:
        return "clarinet"
    if "sax" in text:
        return "saxophone"
    if "trumpet" in text or "cornet" in text:
        return "trumpet"
    if "trombone" in text:
        return "trombone"
    if "guitar" in text:
        return "guitar"
    if "piano" in text or "keyboard" in text:
        return "piano"
    if "voice" in text or "vocal" in text or "sing" in text:
        return "voice"
    if "bass" in text:
        return "bass"
    return "general"


def dedupe_recommendations(items: Sequence[str], *, limit: int = 8) -> list[str]:
    """Drop exact and near-duplicate practice recommendations (order preserved)."""
    out: list[str] = []
    seen_exact: set[str] = set()
    seen_keys: set[str] = set()
    for raw in items:
        text = str(raw or "").strip()
        if not text:
            continue
        exact = text.lower()
        if exact in seen_exact:
            continue
        # Near-dup key: first ~8 significant words
        words = [w for w in exact.replace("—", " ").replace("-", " ").split() if len(w) > 2]
        key = " ".join(words[:8])
        # Also collapse shared stems like breath/backing tempo advice
        if "breath" in exact and "supported air" in exact:
            key = "breath_supported_air"
        if "slow the backing" in exact or ("backing track" in exact and "bpm" in exact and "slow" in exact):
            key = "slow_backing_bpm"
        if "zero buzz" in exact:
            key = "zero_buzz_transition"
        if key in seen_keys:
            continue
        seen_exact.add(exact)
        seen_keys.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out
