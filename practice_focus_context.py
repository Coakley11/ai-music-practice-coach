"""Live Practice Focus coaching context.

Reads the current instrument + Practice Focus from session (via
``practice_setup_globals``) and attaches the SSOT policy profile.

This is a **coaching** context. It must not become an owner of song,
Practice/Concert Key, Written Key, Guitar Shape, backing source,
generated Jam state, or Mission harmony.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from practice_focus_policy import (
    FocusProfile,
    canonical_instrument_label,
    format_focus_prompt_block,
    profile_as_dict,
    resolve_focus_profile,
)


@dataclass(frozen=True)
class PracticeFocusContext:
    instrument: str
    instrument_display: str
    instrument_subtype: str
    focus: str
    category: str
    profile: FocusProfile
    compatible: bool
    ami_prompt_block: str
    analysis_prompt_block: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "instrument_display": self.instrument_display,
            "instrument_subtype": self.instrument_subtype,
            "practice_focus": self.focus,
            "focus_category": self.category,
            "compatible": self.compatible,
            "profile": profile_as_dict(self.profile),
            "ami_prompt_block": self.ami_prompt_block,
            "analysis_prompt_block": self.analysis_prompt_block,
        }


def _instrument_subtype(session_state: Any, instrument: str) -> str:
    try:
        from instrument_transposition import (
            is_transposing_instrument,
            selected_transposing_type,
        )

        if is_transposing_instrument(instrument):
            return str(selected_transposing_type(session_state, instrument) or "").strip()
    except ImportError:
        pass
    return ""


def resolve_practice_focus_context(session_state: Any) -> PracticeFocusContext:
    """Build coaching context from the live session. Never writes musical keys."""
    try:
        from practice_setup_globals import (
            get_active_focus,
            get_active_instrument,
            get_active_instrument_display_name,
        )

        instrument = get_active_instrument(session_state)
        display = get_active_instrument_display_name(session_state)
        focus = get_active_focus(session_state)
    except ImportError:
        instrument = str((session_state or {}).get("instrument") or "").strip()
        display = instrument
        focus = str((session_state or {}).get("focus") or "").strip()

    family = canonical_instrument_label(instrument) or instrument
    profile = resolve_focus_profile(family, focus)
    try:
        from practice_focus_policy import focus_is_compatible

        compatible = focus_is_compatible(family, focus)
    except Exception:
        compatible = bool(focus)
    return PracticeFocusContext(
        instrument=family,
        instrument_display=str(display or family),
        instrument_subtype=_instrument_subtype(session_state, instrument),
        focus=profile.label,
        category=profile.category,
        profile=profile,
        compatible=compatible,
        ami_prompt_block=format_focus_prompt_block(family, profile.label, role="ami"),
        analysis_prompt_block=format_focus_prompt_block(
            family, profile.label, role="analysis"
        ),
    )
