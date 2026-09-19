"""Whole-composition key transposition for Composition Studio."""

from __future__ import annotations

import copy
import re
from typing import Any

from composition_document import ordered_sections, playback_globals, touch_composition
from music_theory import (
    CHROMATIC,
    normalize_root,
    semitone_distance,
    spell_note_in_key,
    transpose_chord,
)

KEY_UNDO_KEY = "composer_key_change_undo"
_PITCH_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")


def _key_root_token(token: str) -> str:
    text = str(token or "C").strip()
    if text.endswith("m") and not text.lower().endswith("maj"):
        return normalize_root(text[:-1]) or "C"
    return normalize_root(text) or "C"


def _key_is_minor(token: str) -> bool:
    text = str(token or "").strip()
    return text.endswith("m") and not text.lower().endswith("maj")


def composition_key_interval(from_token: str, to_token: str) -> int:
    """Semitone steps from old composition key tonic to new (0–11)."""
    return int(semitone_distance(_key_root_token(from_token), _key_root_token(to_token))) % 12


def _transpose_pitch_name(pitch: str, steps: int, *, dest_key: str) -> str:
    text = str(pitch or "").strip()
    if not text or text.lower() == "rest":
        return text
    m = _PITCH_RE.match(text)
    if not m:
        return text
    letter, accidental, octave = m.group(1), m.group(2), m.group(3)
    root = normalize_root(f"{letter}{accidental}")
    if root not in CHROMATIC:
        return text
    midi_base = CHROMATIC.index(root)
    try:
        oct_i = int(octave)
    except ValueError:
        oct_i = 4
    # Approximate absolute MIDI then respell in destination key
    abs_midi = (oct_i + 1) * 12 + midi_base + int(steps)
    new_pc = abs_midi % 12
    new_oct = (abs_midi // 12) - 1
    spelled = spell_note_in_key(new_pc, dest_key)
    return f"{spelled}{new_oct}"


def _transpose_melody_events(
    events: list[dict[str, Any]] | None,
    steps: int,
    *,
    dest_key: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ev in list(events or []):
        if not isinstance(ev, dict):
            continue
        row = copy.deepcopy(ev)
        if row.get("is_rest") or str(row.get("pitch") or "").lower() == "rest":
            out.append(row)
            continue
        midi = row.get("midi")
        try:
            midi_i = int(midi) if midi is not None else None
        except (TypeError, ValueError):
            midi_i = None
        if midi_i is not None:
            midi_i = int(midi_i) + int(steps)
            row["midi"] = midi_i
            row["pitch"] = f"{spell_note_in_key(midi_i % 12, dest_key)}{(midi_i // 12) - 1}"
        else:
            row["pitch"] = _transpose_pitch_name(str(row.get("pitch") or ""), steps, dest_key=dest_key)
        out.append(row)
    return out


def _transpose_chord_entries(
    entries: list[dict[str, Any]] | None,
    steps: int,
    *,
    dest_key: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in list(entries or []):
        if not isinstance(raw, dict):
            continue
        row = copy.deepcopy(raw)
        if row.get("repeat"):
            out.append(row)
            continue
        sym = str(row.get("chord") or "").strip()
        if sym:
            row["chord"] = transpose_chord(sym, steps, reference_key=dest_key)
        out.append(row)
    return out


def snapshot_composition_for_key_undo(doc: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(doc)


def restore_composition_from_key_undo(doc: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return doc
    doc.clear()
    doc.update(copy.deepcopy(snapshot))
    return touch_composition(doc)


def transpose_composition_to_key(
    doc: dict[str, Any],
    new_key_token: str,
    *,
    new_key_label: str = "",
) -> dict[str, Any]:
    """
    Transpose all pitch-bearing material by the interval between old and new key tonics.

    Preserves rhythm, structure, lyrics, qualities (via transpose_chord), and repeat counts.
    Mode policy: major↔minor keeps the chosen destination mode label/token; interval is tonic-only.
    """
    g = doc.setdefault("global", {})
    old_token = str(g.get("original_key_center") or "C")
    new_token = str(new_key_token or old_token).strip() or old_token
    steps = composition_key_interval(old_token, new_token)
    dest_spell_key = new_token

    # Always update key metadata; only shift pitches when interval ≠ 0
    g["original_key_center"] = new_token
    if new_key_label:
        g["original_key_label"] = str(new_key_label)
    # Mode family is locked at song creation — never flip major↔minor here.
    try:
        from composition_document import ensure_original_mode_family

        ensure_original_mode_family(doc)
    except Exception:
        pass
    # Avoid double-transpose marker
    g["last_key_transpose"] = {
        "from": old_token,
        "to": new_token,
        "steps": steps,
    }

    if steps == 0:
        return touch_composition(doc)

    for sec in ordered_sections(doc):
        if not isinstance(sec, dict):
            continue
        if sec.get("chords"):
            sec["chords"] = _transpose_chord_entries(sec.get("chords"), steps, dest_key=dest_spell_key)
        harmony = sec.get("harmony")
        if isinstance(harmony, dict):
            if harmony.get("chord_pattern"):
                harmony["chord_pattern"] = _transpose_chord_entries(
                    harmony.get("chord_pattern"), steps, dest_key=dest_spell_key
                )
        melody = sec.get("melody")
        if isinstance(melody, dict):
            if melody.get("events"):
                melody["events"] = _transpose_melody_events(
                    melody.get("events"), steps, dest_key=dest_spell_key
                )
            if melody.get("melody_pattern"):
                melody["melody_pattern"] = _transpose_melody_events(
                    melody.get("melody_pattern"), steps, dest_key=dest_spell_key
                )
            for phrase in list(melody.get("phrases") or []):
                if not isinstance(phrase, dict):
                    continue
                notes = str(phrase.get("notes") or "").strip()
                if notes:
                    parts = []
                    for tok in notes.split():
                        if re.match(r"^[A-Ga-g](?:#|b)?\d+$", tok):
                            parts.append(_transpose_pitch_name(tok, steps, dest_key=dest_spell_key))
                        else:
                            try:
                                parts.append(transpose_chord(tok, steps, reference_key=dest_spell_key))
                            except Exception:
                                parts.append(tok)
                    phrase["notes"] = " ".join(parts)

    return touch_composition(doc)


def apply_song_key_change(
    session: dict[str, Any],
    doc: dict[str, Any],
    new_key_token: str,
    *,
    new_key_label: str = "",
    push_undo: bool = True,
) -> dict[str, Any]:
    """Atomic song-wide key change: transpose material + invalidate stale proposals.

    Destination key is coerced into the Composition's locked original_mode_family
    (major songs stay major; minor songs stay minor). Practice Key is ignored.
    """
    from composition_document import (
        coerce_composition_key_choice_for_doc,
        composition_key_token_from_choice,
        ensure_original_mode_family,
    )

    ensure_original_mode_family(doc)
    label = str(new_key_label or "").strip() or str(new_key_token or "")
    locked_label = coerce_composition_key_choice_for_doc(doc, label)
    locked_token = composition_key_token_from_choice(locked_label)
    if push_undo:
        push_key_undo(session, doc)
    transpose_composition_to_key(doc, locked_token, new_key_label=locked_label)
    _invalidate_key_sensitive_session_state(session)
    return doc


def apply_song_tempo_change(doc: dict[str, Any], new_bpm: int) -> dict[str, Any]:
    """Atomic song-wide BPM update (beat relationships preserved)."""
    from composition_document import coerce_composition_bpm

    g = doc.setdefault("global", {})
    g["bpm"] = coerce_composition_bpm(new_bpm)
    return touch_composition(doc)


def _invalidate_key_sensitive_session_state(session: dict[str, Any]) -> None:
    """Drop pending proposals / widget caches that would still show the old key."""
    drop_prefixes = (
        "composer_refine_proposal_",
        "composer_melody_refine_proposal_",
        "composer_melody_editor_draft_",
        "composer_hum_proposal_",
        "composer_chord_suggest_",
        "composer_melody_suggest_",
        "composer_melody_ed_nl_choice_",
    )
    for key in list(session.keys()):
        sk = str(key)
        if any(sk.startswith(p) for p in drop_prefixes):
            session.pop(key, None)
    try:
        from composition_preview import invalidate_composer_preview

        invalidate_composer_preview(session)
    except Exception:
        session.pop("composer_preview_wav", None)
        session.pop("composer_preview_sig", None)


def push_key_undo(session: dict[str, Any], doc: dict[str, Any]) -> None:
    session[KEY_UNDO_KEY] = snapshot_composition_for_key_undo(doc)


def apply_undo_key_change(session: dict[str, Any], doc: dict[str, Any]) -> bool:
    snap = session.pop(KEY_UNDO_KEY, None)
    if not isinstance(snap, dict):
        return False
    restore_composition_from_key_undo(doc, snap)
    return True
