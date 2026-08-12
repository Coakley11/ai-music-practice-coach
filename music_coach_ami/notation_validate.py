"""Reusable AMI notation structure invariants for conventional staff music."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


_DURATION_UNIT = {
    "": 1.0,  # default L: length
    "1": 4.0,
    "2": 2.0,
    "4": 1.0,
    "/2": 0.5,
    "1/2": 2.0,  # rarely used as suffix when L=1/4; kept for robustness
}


def meter_beats(meter: str) -> float:
    text = str(meter or "4/4").strip()
    if "/" not in text:
        return 4.0
    num, den = text.split("/", 1)
    try:
        return (float(num) * 4.0) / float(den)
    except (TypeError, ValueError):
        return 4.0


def _token_beats(token: str, *, default_len: str = "1/4") -> float:
    """Approximate beat length of one ABC pitch token relative to quarter=1 when L:1/4."""
    raw = str(token or "").strip()
    if not raw or raw in {"|", "||", "|]", "[|"}:
        return 0.0
    raw = re.sub(r'"[^"]*"', "", raw)
    m = re.search(r"([A-Ga-g][,']*)(\d*/?\d*)$", raw)
    if not m:
        return 0.0
    suffix = m.group(2)
    if suffix == "" or suffix is None:
        return 1.0
    if suffix == "2":
        return 2.0
    if suffix == "3":
        return 3.0
    if suffix == "4":
        return 4.0
    if suffix in {"/2", "/"}:
        return 0.5
    if suffix == "/4":
        return 0.25
    if "/" in suffix:
        try:
            a, b = suffix.split("/", 1)
            return float(a or 1) / float(b or 1)
        except (TypeError, ValueError):
            return 1.0
    try:
        return float(suffix)
    except (TypeError, ValueError):
        return 1.0


def _music_body(abc: str) -> str:
    lines = str(abc or "").splitlines()
    body: list[str] = []
    seen_key = False
    for line in lines:
        if line.startswith("K:"):
            seen_key = True
            continue
        if not seen_key:
            continue
        if line.startswith(("X:", "T:", "M:", "L:", "Q:", "K:", "%%")):
            continue
        body.append(line)
    return " ".join(body)


def extract_measures(abc: str) -> list[str]:
    body = _music_body(abc)
    # Split on bar lines; drop empty trailing
    parts = re.split(r"\|+", body)
    return [p.strip() for p in parts if p.strip()]


@dataclass
class NotationValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    measure_count: int = 0
    meter: str = "4/4"
    clef: str = ""


def validate_notation_structure(
    abc: str,
    *,
    meter: str = "4/4",
    clef: str = "",
    profile: Any = None,
    raise_on_error: bool = False,
) -> NotationValidationResult:
    """Validate conventional AMI sheet-music ABC for meter, bars, clef, and register."""
    errors: list[str] = []
    warnings: list[str] = []
    text = str(abc or "")
    if not text.strip():
        errors.append("empty_abc")
        result = NotationValidationResult(ok=False, errors=errors, meter=meter, clef=clef)
        if raise_on_error:
            raise ValueError("; ".join(errors))
        return result

    if "M:" not in text:
        errors.append("missing_meter")
    if "K:" not in text:
        errors.append("missing_key")
    if clef and f"clef={clef}" not in text and f"clef={clef}" not in text.replace(" ", ""):
        # Allow K: line without explicit clef only when caller did not require one
        if "clef=" not in text:
            warnings.append("missing_clef_token")

    if "|" not in text:
        errors.append("missing_bar_lines")

    expected = meter_beats(meter)
    measures = extract_measures(text)
    for i, measure in enumerate(measures):
        tokens = [t for t in measure.split() if t and not t.startswith("\"")]
        # tokens may still include chord-prefixed pitches like "Cm7"C,
        # already stripped quotes above via split — chord symbols stick to pitches
        # Re-tokenize: split on spaces after removing embedded chord labels for beat math
        beat_tokens = re.findall(
            r'"[^"]*"|(?:[=_^]+)?[A-Ga-g][,\'=_\^]*\d*/?\d*',
            measure,
        )
        total = 0.0
        for tok in beat_tokens:
            if tok.startswith('"') and tok.endswith('"'):
                continue
            total += _token_beats(tok)
        if measures and abs(total - expected) > 0.01 and total > 0:
            # Incomplete final pickup bars are warned, not hard-failed
            if i == len(measures) - 1 and total < expected:
                warnings.append(f"measure_{i+1}_incomplete:{total}/{expected}")
            else:
                errors.append(f"measure_{i+1}_beats:{total}/{expected}")

    # Register: reject leading-comma lowercase (legacy bug) and extreme apostrophe runs
    if re.search(r",[a-g]", text):
        errors.append("invalid_abc_octave_leading_comma_lowercase")
    if re.search(r"[A-G]'{3,}", text) or re.search(r"[a-g]'{3,}", text):
        warnings.append("extreme_ledger_apostrophes")

    if profile is not None:
        midi_low = int(getattr(profile, "midi_low", 0) or 0)
        midi_high = int(getattr(profile, "midi_high", 0) or 0)
        if midi_low and midi_high and midi_high < midi_low:
            errors.append("invalid_profile_midi_range")

    ok = not errors
    result = NotationValidationResult(
        ok=ok,
        errors=errors,
        warnings=warnings,
        measure_count=len(measures),
        meter=meter,
        clef=clef or "",
    )
    if raise_on_error and not ok:
        raise ValueError("; ".join(errors))
    return result
