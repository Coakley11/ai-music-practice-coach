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


def build_analysis_status_message(
    ctx: dict[str, Any] | None = None,
    *,
    mission_ids: Sequence[str] | None = None,
    multitrack: bool = False,
) -> str:
    """Compose a concise spinner/status line from selected criteria + Focuses + baselines."""
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

    ids = [str(x).strip() for x in (mission_ids or ctx.get("mission_ids") or []) if str(x).strip()]
    improv_active = bool(ids)

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
    if improv_active and "improvisation missions" not in {p.lower() for p in parts}:
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


def has_song_form_context(ctx: dict[str, Any] | None) -> bool:
    """True when Upload-selected song has real sections/chords (not Other / exercise-only)."""
    ctx = dict(ctx or {})
    source = str(ctx.get("song_source_type") or "").strip().lower()
    if "other" in source or "not a song" in source:
        return False
    sections = ctx.get("sections")
    has_sections = isinstance(sections, dict) and any(str(k).strip() for k in sections.keys())
    chords = ctx.get("target_chords") or []
    has_chords = isinstance(chords, (list, tuple)) and any(str(c).strip() for c in chords)
    return bool(has_sections or has_chords)


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
