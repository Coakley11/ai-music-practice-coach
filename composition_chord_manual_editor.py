"""Manual / advanced chord editor helpers for Composition Studio sections."""

from __future__ import annotations

import copy
import re
from typing import Any

from custom_progression_lab import expand_entries_to_chords, normalize_chord_symbol
from music_theory import (
    CHROMATIC,
    chord_root_for_theory,
    normalize_chord_for_theory,
    normalize_root,
    spell_note_in_key,
)

DRAFT_KEY_PREFIX = "composer_chord_editor_draft_"
UNDO_KEY_PREFIX = "composer_chord_editor_undo_"

QUALITY_OPTIONS: tuple[str, ...] = (
    "",
    "m",
    "7",
    "maj7",
    "m7",
    "m7b5",
    "dim",
    "dim7",
    "aug",
    "sus2",
    "sus4",
    "add9",
    "6",
    "m6",
    "9",
    "m9",
    "maj9",
)

ALTERATION_OPTIONS: tuple[str, ...] = ("", "b5", "#5", "b9", "#9", "#11", "b13")

ROOT_OPTIONS: tuple[str, ...] = (
    "C",
    "C#",
    "Db",
    "D",
    "D#",
    "Eb",
    "E",
    "F",
    "F#",
    "Gb",
    "G",
    "G#",
    "Ab",
    "A",
    "A#",
    "Bb",
    "B",
)


def draft_key(section_id: str) -> str:
    return f"{DRAFT_KEY_PREFIX}{section_id}"


def undo_key(section_id: str) -> str:
    return f"{UNDO_KEY_PREFIX}{section_id}"


def _beats_per_bar(meter: str) -> float:
    text = str(meter or "4/4")
    if "/" in text:
        try:
            num, den = text.split("/", 1)
            n = float(num)
            d = float(den)
            if d == 8 and n in (6, 9, 12):
                return n  # treat compound as n eighth-note units displayed as beats
            return n * (4.0 / d)
        except ValueError:
            pass
    return 4.0


def chord_timeline(
    entries: list[dict[str, Any]] | None,
    *,
    meter: str = "4/4",
) -> list[dict[str, Any]]:
    """Return progression rows with measure/beat locations (1-based measure)."""
    bpb = max(1.0, _beats_per_bar(meter))
    rows: list[dict[str, Any]] = []
    beat_cursor = 0.0
    last_chord = ""
    for i, raw in enumerate(list(entries or [])):
        if not isinstance(raw, dict):
            continue
        bars = max(1, int(raw.get("bars") or 1))
        if raw.get("repeat"):
            symbol = last_chord or "%"
        else:
            symbol = normalize_chord_symbol(str(raw.get("chord") or "")) or str(raw.get("chord") or "").strip()
            last_chord = symbol or last_chord
        start_measure = int(beat_cursor // bpb) + 1
        start_beat = (beat_cursor % bpb) + 1.0
        duration_beats = bars * bpb
        rows.append(
            {
                "index": i,
                "chord": symbol,
                "bars": bars,
                "measure": start_measure,
                "beat": round(start_beat, 2),
                "duration_beats": duration_beats,
                "chromatic": False,
            }
        )
        beat_cursor += duration_beats
    return rows


def parse_chord_parts(symbol: str) -> dict[str, str]:
    """Split a chord symbol into editable parts (best-effort)."""
    text = normalize_chord_symbol(symbol) or str(symbol or "").strip()
    if not text:
        return {"root": "C", "quality": "", "alteration": "", "bass": "", "raw": ""}
    bass = ""
    if "/" in text:
        text, bass = text.split("/", 1)
        bass = normalize_root(bass) or bass.strip()
    m = re.match(r"^([A-Ga-g](?:#|b)?)(.*)$", text)
    if not m:
        return {"root": "C", "quality": text, "alteration": "", "bass": bass, "raw": text}
    root = normalize_root(m.group(1)) or m.group(1)
    rest = m.group(2) or ""
    quality = ""
    alteration = ""
    for q in sorted(QUALITY_OPTIONS, key=len, reverse=True):
        if q and rest.startswith(q):
            quality = q
            rest = rest[len(q) :]
            break
    for alt in sorted(ALTERATION_OPTIONS, key=len, reverse=True):
        if alt and alt in rest:
            alteration = alt
            rest = rest.replace(alt, "", 1)
            break
    if rest and not quality:
        quality = rest
        rest = ""
    elif rest and not alteration:
        alteration = rest
    return {"root": root, "quality": quality, "alteration": alteration, "bass": bass, "raw": text}


def build_chord_symbol(
    *,
    root: str,
    quality: str = "",
    alteration: str = "",
    bass: str = "",
) -> str:
    r = normalize_root(root) or str(root or "C").strip() or "C"
    q = str(quality or "").strip()
    alt = str(alteration or "").strip()
    body = f"{r}{q}{alt}"
    b = normalize_root(bass) if bass else ""
    if b:
        body = f"{body}/{b}"
    return normalize_chord_symbol(body) or body


def _scale_pitch_classes(key_token: str) -> set[int]:
    token = str(key_token or "C").strip()
    minor = token.endswith("m") and not token.lower().endswith("maj")
    root = normalize_root(token.rstrip("m")) or "C"
    if root not in CHROMATIC:
        return set(range(12))
    idx = CHROMATIC.index(root)
    intervals = (0, 2, 3, 5, 7, 8, 10) if minor else (0, 2, 4, 5, 7, 9, 11)
    return {(idx + i) % 12 for i in intervals}


def is_chromatic_to_key(symbol: str, key_token: str) -> bool:
    theory = normalize_chord_for_theory(symbol)
    root = chord_root_for_theory(theory) or normalize_root(symbol)
    if not root or root not in CHROMATIC:
        return False
    return CHROMATIC.index(root) not in _scale_pitch_classes(key_token)


def annotate_chromatic(rows: list[dict[str, Any]], key_token: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        item["chromatic"] = is_chromatic_to_key(str(item.get("chord") or ""), key_token)
        out.append(item)
    return out


def suggest_insert_chords(
    *,
    key_token: str,
    before: str = "",
    after: str = "",
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Context-aware insert suggestions (diatonic neighbors + common motions)."""
    token = str(key_token or "C").strip()
    minor = token.endswith("m") and not token.lower().endswith("maj")
    root = normalize_root(token.rstrip("m")) or "C"
    if root not in CHROMATIC:
        root = "C"
    idx = CHROMATIC.index(root)

    def spell(pc: int) -> str:
        return spell_note_in_key(pc % 12, token)

    if minor:
        diatonic = [
            f"{spell(idx)}m",
            f"{spell(idx + 3)}",
            f"{spell(idx + 5)}m",
            f"{spell(idx + 7)}m",
            f"{spell(idx + 8)}",
            f"{spell(idx + 10)}",
            f"{spell(idx + 2)}dim",
        ]
    else:
        diatonic = [
            f"{spell(idx)}",
            f"{spell(idx + 2)}m",
            f"{spell(idx + 4)}m",
            f"{spell(idx + 5)}",
            f"{spell(idx + 7)}",
            f"{spell(idx + 9)}m",
            f"{spell(idx + 11)}dim",
        ]

    ideas: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(sym: str, why: str, *, chromatic: bool = False) -> None:
        n = normalize_chord_symbol(sym) or sym
        if not n or n in seen:
            return
        seen.add(n)
        ideas.append(
            {
                "chord": n,
                "why": why,
                "chromatic": chromatic or is_chromatic_to_key(n, token),
            }
        )

    for sym in diatonic:
        _add(sym, "Fits the song key")

    prev = normalize_chord_symbol(before) or before
    nxt = normalize_chord_symbol(after) or after
    if prev:
        pr = chord_root_for_theory(normalize_chord_for_theory(prev))
        if pr and pr in CHROMATIC:
            pidx = CHROMATIC.index(pr)
            _add(f"{spell(pidx + 7)}7", "Dominant of previous chord", chromatic=True)
            _add(f"{spell(pidx)}sus4", "Suspension from previous")
    if nxt:
        nr = chord_root_for_theory(normalize_chord_for_theory(nxt))
        if nr and nr in CHROMATIC:
            nidx = CHROMATIC.index(nr)
            _add(f"{spell(nidx + 7)}7", "Sets up next chord", chromatic=True)

    _add(f"{spell(idx + 1)}", "Chromatic neighbor (outside key)", chromatic=True)
    _add(f"{spell(idx + 6)}7", "Tritone color (outside key)", chromatic=True)
    return ideas[: max(1, int(limit))]


def snapshot_entries(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return copy.deepcopy(list(entries or []))


def ensure_draft(
    session: dict[str, Any],
    section_id: str,
    entries: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    key = draft_key(section_id)
    draft = session.get(key)
    if not isinstance(draft, list):
        draft = snapshot_entries(entries)
        session[key] = draft
    return draft


def clear_draft(session: dict[str, Any], section_id: str) -> None:
    session.pop(draft_key(section_id), None)


def push_undo(
    session: dict[str, Any],
    section_id: str,
    entries: list[dict[str, Any]] | None,
) -> None:
    key = undo_key(section_id)
    stack = list(session.get(key) or [])
    stack.append(snapshot_entries(entries))
    session[key] = stack[-20:]


def pop_undo(session: dict[str, Any], section_id: str) -> list[dict[str, Any]] | None:
    key = undo_key(section_id)
    stack = list(session.get(key) or [])
    if not stack:
        return None
    prev = stack.pop()
    session[key] = stack
    return prev if isinstance(prev, list) else None


def update_draft_chord(
    draft: list[dict[str, Any]],
    index: int,
    *,
    chord: str | None = None,
    bars: int | None = None,
) -> list[dict[str, Any]]:
    out = snapshot_entries(draft)
    if index < 0 or index >= len(out):
        return out
    row = dict(out[index]) if isinstance(out[index], dict) else {"chord": "", "bars": 1}
    if chord is not None:
        row.pop("repeat", None)
        row["chord"] = normalize_chord_symbol(chord) or str(chord).strip()
    if bars is not None:
        row["bars"] = max(1, int(bars))
    out[index] = row
    return out


def insert_draft_chord(
    draft: list[dict[str, Any]],
    index: int,
    chord: str,
    *,
    bars: int = 1,
) -> list[dict[str, Any]]:
    out = snapshot_entries(draft)
    idx = max(0, min(int(index), len(out)))
    out.insert(
        idx,
        {
            "chord": normalize_chord_symbol(chord) or str(chord).strip(),
            "bars": max(1, int(bars)),
        },
    )
    return out


def remove_draft_chord(draft: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    out = snapshot_entries(draft)
    if 0 <= index < len(out):
        out.pop(index)
    return out


def draft_playback_chords(draft: list[dict[str, Any]] | None) -> list[str]:
    return expand_entries_to_chords(draft)
