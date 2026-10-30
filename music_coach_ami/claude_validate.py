"""Schema and factual-grounding validation for Claude enrichment. All-or-nothing: any violation rejects it."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from music_coach_ami.claude_facts import FactSheet

MAX_WHY = 320
MAX_GUIDANCE_ITEM = 260
MAX_LISTEN_ITEM = 200
GUIDANCE_RANGE = (2, 4)
LISTEN_MAX = 3
_MAX_VIOLATIONS = 12

ENRICHMENT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "why_this_fits": {"type": "string"},
        "guidance": {"type": "array", "items": {"type": "string"}},
        "listen_for": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["why_this_fits", "guidance", "listen_for"],
    "additionalProperties": False,
}

_MARKER = re.compile(r"\{\{\s*(chord|key|section|bpm)\s*:\s*([^{}]{1,40}?)\s*\}\}")
_CHORD_LIKE = re.compile(
    r"(?<![\w/#♯♭])[A-G](?:[#b♯♭])?(?:maj|min|dim|aug|sus|add|m|M|ø|°|\+|-)?(?:\d{1,2})?"
    r"(?:[#b♯♭]\d{1,2})*(?:/[A-G][#b♯♭]?)?(?![\w#♯♭])"
)
_SPOKEN_ACCIDENTAL = re.compile(r"\b[A-G]\s+(?:flat|sharp)\b", re.I)
_THEORY_WORDS = re.compile(
    r"\b(dorian|mixolydian|lydian|phrygian|locrian|aeolian|ionian|altered|pentatonic|bebop|"
    r"whole[- ]tone|blues scale|harmonic minor|melodic minor|chromatic scale|diminished scale)\b",
    re.I,
)
_UNSUPPORTED_CLAIMS = re.compile(
    r"(modulat\w*|key change|relative (?:major|minor)|recording|original version|studio version)", re.I
)
_BAR_REFERENCE = re.compile(r"\b(?:bar|measure)s?\s+\d+", re.I)
_PLAIN_BPM = re.compile(r"(\d{2,3})\s*bpm", re.I)
_FORMAT_BAD = (
    ("url", re.compile(r"https?://|www\.", re.I)),
    ("link", re.compile(r"\]\(")),
    ("code_fence", re.compile(r"```|`")),
    ("html", re.compile(r"[<>]")),
    ("emphasis", re.compile(r"\*")),
    ("heading", re.compile(r"^\s*#", re.M)),
    ("newline", re.compile(r"[\r\n]")),
    ("control_char", re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")),
)


@dataclass(frozen=True)
class ValidatedEnrichment:
    why: str
    guidance: tuple[str, ...]
    listen_for: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"why": self.why, "guidance": list(self.guidance), "listen_for": list(self.listen_for)}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    violations: tuple[str, ...]
    enrichment: ValidatedEnrichment | None = None


def parse_payload_text(text: str) -> Any:
    """Parse the model's JSON text; raises ValueError on anything that is not a single JSON value."""
    return json.loads(text)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _check_text(text: str, facts: FactSheet, violations: list[str]) -> str:
    """Validate one text item and return its display form (markers rendered)."""
    for kind, pattern in _FORMAT_BAD:
        if pattern.search(text):
            violations.append(f"format:{kind}")

    allowed_chords = facts.allowed_chords()
    allowed_keys = facts.allowed_keys()
    allowed_sections = facts.allowed_sections()
    allowed_bpm = set(facts.allowed_bpm)

    def render(match: re.Match[str]) -> str:
        kind, value = match.group(1), match.group(2).strip()
        if kind == "chord":
            if value not in allowed_chords:
                violations.append(f"chord_not_in_facts:{value}")
            return f"**{value}**"
        if kind == "key":
            if _norm(value) not in allowed_keys:
                violations.append(f"key_not_in_facts:{value}")
            return f"**{value}**"
        if kind == "section":
            if _norm(value) not in allowed_sections:
                violations.append(f"section_not_in_facts:{value}")
            return f"**{value}**"
        try:
            bpm = int(value)
        except ValueError:
            violations.append(f"bpm_not_numeric:{value}")
            return value
        if bpm not in allowed_bpm:
            violations.append(f"bpm_not_in_facts:{bpm}")
        return f"{bpm} BPM"

    rendered = _MARKER.sub(render, text)
    stripped = _MARKER.sub(" ", text)

    if "{{" in stripped or "}}" in stripped:
        violations.append("malformed_marker")
    for match in _CHORD_LIKE.finditer(stripped):
        if match.group(0) != "A":
            violations.append(f"unmarked_musical_token:{match.group(0)}")
    if _SPOKEN_ACCIDENTAL.search(stripped):
        violations.append("unmarked_note_name")
    for match in _THEORY_WORDS.finditer(stripped):
        violations.append(f"unsupported_theory:{match.group(0).lower()}")
    for match in _UNSUPPORTED_CLAIMS.finditer(stripped):
        violations.append(f"unsupported_claim:{match.group(0).lower()}")
    if _BAR_REFERENCE.search(stripped):
        violations.append("unsupported_bar_reference")
    for match in _PLAIN_BPM.finditer(stripped):
        if int(match.group(1)) not in allowed_bpm:
            violations.append(f"bpm_not_in_facts:{match.group(1)}")
    return rendered.strip()


def _string_list(value: Any, name: str, violations: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        violations.append(f"schema:{name}_not_string_list")
        return []
    return value


def validate_enrichment(raw: Any, facts: FactSheet) -> ValidationResult:
    violations: list[str] = []
    if not isinstance(raw, dict):
        return ValidationResult(False, ("schema:not_object",))
    allowed_keys = {"why_this_fits", "guidance", "listen_for"}
    for extra in sorted(set(raw) - allowed_keys):
        violations.append(f"schema:extra_key:{extra}")
    why = raw.get("why_this_fits")
    if not isinstance(why, str) or not why.strip():
        violations.append("schema:why_this_fits_missing")
        why = ""
    guidance = _string_list(raw.get("guidance", None), "guidance", violations)
    listen = _string_list(raw.get("listen_for", []), "listen_for", violations)

    if len(why) > MAX_WHY:
        violations.append("schema:why_too_long")
    if not (GUIDANCE_RANGE[0] <= len(guidance) <= GUIDANCE_RANGE[1]):
        violations.append("schema:guidance_count")
    if len(listen) > LISTEN_MAX:
        violations.append("schema:listen_for_count")
    for item in guidance:
        if not item.strip():
            violations.append("schema:empty_guidance_item")
        elif len(item) > MAX_GUIDANCE_ITEM:
            violations.append("schema:guidance_item_too_long")
    for item in listen:
        if not item.strip():
            violations.append("schema:empty_listen_item")
        elif len(item) > MAX_LISTEN_ITEM:
            violations.append("schema:listen_item_too_long")

    why_out = _check_text(why, facts, violations) if why else ""
    guidance_out = tuple(_check_text(g, facts, violations) for g in guidance)
    listen_out = tuple(_check_text(g, facts, violations) for g in listen)

    unique: list[str] = []
    for code in violations:
        if code not in unique:
            unique.append(code)
    if unique:
        return ValidationResult(False, tuple(unique[:_MAX_VIOLATIONS]))
    return ValidationResult(True, (), ValidatedEnrichment(why_out, guidance_out, listen_out))
