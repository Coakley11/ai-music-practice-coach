"""Historical Practice Focus snapshots.

Current Practice Focus (session ``focus``) is mutable.

Historical artifacts (Practice Log rows, upload analyses) must copy a
**frozen** snapshot at write time. Changing today's selector must not
rewrite yesterday's analysis.

Missing historical focus stays missing — never invent one from the
current selector.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from practice_focus_policy import (
    canonical_instrument_label,
    category_for_focus,
    resolve_focus_profile,
)

SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_KEY = "practice_focus_snapshot"
ANALYSIS_FOCUS_LABEL_KEY = "practice_focus_at_analysis"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def capture_practice_focus_snapshot(
    session_state: Any,
    *,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Frozen copy of the *current* coaching focus for a new artifact."""
    from practice_focus_context import resolve_practice_focus_context

    ctx = resolve_practice_focus_context(session_state)
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "instrument": ctx.instrument,
        "instrument_display": ctx.instrument_display,
        "instrument_subtype": ctx.instrument_subtype,
        "practice_focus": ctx.focus,
        "focus_category": ctx.category,
        "captured_at": str(captured_at or _utc_now_iso()),
    }


def snapshot_from_historical_fields(
    *,
    instrument: Any = "",
    practice_focus: Any = "",
    captured_at: Any = "",
    instrument_display: Any = "",
    instrument_subtype: Any = "",
) -> dict[str, Any] | None:
    """Wrap fields already stored on an old artifact. Does not invent a focus."""
    focus = str(practice_focus or "").strip()
    if not focus:
        return None
    inst_raw = str(instrument or "").strip()
    family = canonical_instrument_label(inst_raw) or inst_raw
    profile = resolve_focus_profile(family, focus)
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "instrument": family,
        "instrument_display": str(instrument_display or inst_raw or family),
        "instrument_subtype": str(instrument_subtype or "").strip(),
        "practice_focus": profile.label,
        "focus_category": profile.category,
        "captured_at": str(captured_at or "").strip(),
    }


def read_practice_focus_snapshot(raw: Any) -> dict[str, Any] | None:
    """Return a normalized snapshot dict, or None if focus was never stored."""
    if not isinstance(raw, Mapping):
        return None
    focus = str(raw.get("practice_focus") or raw.get("focus") or "").strip()
    if not focus:
        return None
    inst = str(raw.get("instrument") or "").strip()
    family = canonical_instrument_label(inst) or inst
    category = str(raw.get("focus_category") or "").strip() or category_for_focus(focus)
    return {
        "schema_version": int(raw.get("schema_version") or SNAPSHOT_SCHEMA_VERSION),
        "instrument": family,
        "instrument_display": str(raw.get("instrument_display") or inst or family),
        "instrument_subtype": str(raw.get("instrument_subtype") or "").strip(),
        "practice_focus": focus,
        "focus_category": category,
        "captured_at": str(raw.get("captured_at") or "").strip(),
    }


def stamp_analysis_result_with_focus(
    result: Mapping[str, Any] | None,
    session_state: Any,
    *,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Copy current focus onto a new analysis result. Does not mutate *result*."""
    out = dict(result or {})
    snap = capture_practice_focus_snapshot(session_state, captured_at=captured_at)
    out[SNAPSHOT_KEY] = snap
    out[ANALYSIS_FOCUS_LABEL_KEY] = snap.get("practice_focus") or ""
    return out


def historical_focus_prompt_block(snapshot: Any, *, current_focus: str = "") -> str:
    """Prompt fragment for weekly/log analysis over frozen snapshots."""
    snap = read_practice_focus_snapshot(snapshot)
    if snap is None:
        return (
            "This record has no stored Practice Focus. Do not invent one from "
            "the user's current selector."
        )
    from practice_focus_policy import format_focus_prompt_block

    block = format_focus_prompt_block(
        snap.get("instrument") or "",
        snap.get("practice_focus") or "",
        role="history",
    )
    current = str(current_focus or "").strip()
    stored = str(snap.get("practice_focus") or "").strip()
    if current and stored and current != stored:
        block += (
            f"\n- Historical Practice Focus on this record: {stored}. "
            f"Current Practice Focus is now {current}. Distinguish them."
        )
    return block
