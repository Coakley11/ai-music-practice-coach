"""Resolve instrument identity vs notation realization (base family vs sax subtype)."""

from __future__ import annotations

from typing import Any


def _clean(text: object) -> str:
    return str(text or "").strip()


def resolve_transposing_subtype(
    session_state: dict[str, Any] | None,
    instrument: str,
) -> str:
    """Canonical sax/trumpet/clarinet subtype from app SSOT (empty when N/A)."""
    inst = _clean(instrument)
    if not inst:
        return ""
    try:
        from instrument_transposition import (
            is_transposing_instrument,
            selected_transposing_type,
        )
        from music_coach_ami.session_access import as_session_mapping

        session = as_session_mapping(session_state)
        # Display labels like "Alto Sax" still need subtype resolution via base family.
        base = _base_instrument_family(inst)
        if not is_transposing_instrument(base) and not is_transposing_instrument(inst):
            # Explicit subtype label already (Alto Saxophone, Bb Clarinet, …).
            if any(x in inst.lower() for x in ("sax", "clarinet", "trumpet")):
                return _type_label_from_display(inst)
            return ""
        target = base if is_transposing_instrument(base) else inst
        return _clean(selected_transposing_type(session, target))
    except ImportError:
        return _type_label_from_display(inst)


def _base_instrument_family(instrument: str) -> str:
    low = instrument.lower()
    if "sax" in low:
        return "Saxophone"
    if "clarinet" in low:
        return "Clarinet"
    if "trumpet" in low or "flugel" in low:
        return "Trumpet"
    return instrument


def _type_label_from_display(instrument: str) -> str:
    low = instrument.lower()
    if "tenor" in low and "sax" in low:
        return "Tenor saxophone (Bb)"
    if "soprano" in low and "sax" in low:
        return "Soprano saxophone (Bb)"
    if "bari" in low and "sax" in low:
        return "Baritone saxophone (Eb)"
    if "alto" in low and "sax" in low:
        return "Alto saxophone (Eb)"
    if "clarinet" in low:
        return "Bb Clarinet"
    if "trumpet" in low:
        return "Bb Trumpet"
    return ""


def notation_instrument_name(
    instrument: str,
    *,
    session_state: dict[str, Any] | None = None,
    transposing_subtype: str = "",
) -> str:
    """Name used for NotationProfile / register (Alto Saxophone ≠ generic Saxophone)."""
    inst = _clean(instrument) or "Piano"
    subtype = _clean(transposing_subtype) or resolve_transposing_subtype(session_state, inst)
    if not subtype:
        return inst
    try:
        from instrument_transposition import instrument_display_name

        base = _base_instrument_family(inst)
        display = _clean(instrument_display_name(subtype, base))
        return display or inst
    except ImportError:
        return inst


def realization_diagnostics(
    instrument: str,
    *,
    session_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = _base_instrument_family(_clean(instrument))
    subtype = resolve_transposing_subtype(session_state, instrument)
    notation_name = notation_instrument_name(
        instrument, session_state=session_state, transposing_subtype=subtype
    )
    return {
        "base_instrument": base if "sax" in base.lower() or base != _clean(instrument) else _clean(instrument),
        "selected_instrument": _clean(instrument),
        "selected_transposing_subtype": subtype or None,
        "notation_instrument": notation_name,
        "subtype_resolved": bool(subtype) if "sax" in _clean(instrument).lower() else None,
    }
