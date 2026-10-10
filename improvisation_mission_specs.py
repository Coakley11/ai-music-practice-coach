"""Mission hard constraints — validate phrases before display."""

from __future__ import annotations

from typing import Any

from music_theory import classify_chord_quality, normalize_root, split_chord
from improvisation_mission_rules import (
    _blues_relationship_for_quality,
    _chord_tone_pcs,
    _guide_third_seventh,
    _pentatonic_relationship_for_quality,
    resolve_blues_choice,
    resolve_pentatonic_choice,
)
from improvisation_motif import _midi_from_note, _parse_key_scale, chord_tone_names, motif_rhythm_symbols


def _pitch_classes(notes: list[str]) -> list[int]:
    out: list[int] = []
    for n in notes:
        root, _ = split_chord(str(n))
        from music_theory import NOTE_TO_MIDI

        out.append(NOTE_TO_MIDI.get(normalize_root(root), 60) % 12)
    return out


def _max_consecutive_scale_steps(notes: list[str], *, key_center: str) -> int:
    _mode, scale_pcs = _parse_key_scale(key_center)
    if not scale_pcs:
        return 0
    ordered = sorted(scale_pcs)
    pcs = _pitch_classes(notes)
    if len(pcs) < 2:
        return 0
    best = 1
    run = 1
    for i in range(1, len(pcs)):
        prev, cur = pcs[i - 1], pcs[i]
        step = min((cur - prev) % 12, (prev - cur) % 12)
        if step in (1, 2):
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


def _stepwise_ratio(notes: list[str], *, key_center: str) -> float:
    pcs = _pitch_classes(notes)
    if len(pcs) < 2:
        return 0.0
    steps = 0
    scale_like = 0
    for i in range(1, len(pcs)):
        diff = abs(pcs[i] - pcs[i - 1])
        diff = min(diff, 12 - diff)
        steps += 1
        if diff <= 2:
            scale_like += 1
    return scale_like / steps if steps else 0.0


def validate_mission_motif(
    mission: str,
    motif: dict[str, Any],
    *,
    chord: str,
    key_center: str,
) -> tuple[bool, str]:
    """Return (passes, reason). Hard missions must pass before display."""
    low = str(mission or "").lower()
    notes = [str(n) for n in (motif.get("notes") or []) if str(n).strip()]
    if not notes:
        return False, "empty phrase"

    allowed = _chord_tone_pcs(chord, key_center=key_center)
    pcs = set(_pitch_classes(notes))

    if "chord tone" in low and "only" in low:
        if not pcs.issubset(allowed):
            return False, "non-chord-tone pitch"
        return True, ""

    if "guide tone" in low:
        guides = {_pitch_classes([g])[0] for g in _guide_third_seventh(chord, key_center=key_center) if g}
        if not pcs.issubset(guides):
            return False, "not guide tones only"
        return True, ""

    if "5 notes" in low and "register" in low:
        if len(pcs) > 5:
            return False, "too many pitch classes"
        midis = [_midi_from_note(n, 4) for n in notes]
        if max(midis) - min(midis) > 12:
            return False, "register span too wide"
        return True, ""

    if "scalar" in low and "only" in low:
        if _stepwise_ratio(notes, key_center=key_center) < 0.75:
            return False, "not enough stepwise motion"
        leaps = [
            min(abs(_pitch_classes(notes)[i] - _pitch_classes(notes)[i - 1]), 12 - abs(_pitch_classes(notes)[i] - _pitch_classes(notes)[i - 1]))
            for i in range(1, len(notes))
        ]
        if any(x > 4 for x in leaps):
            return False, "arpeggio leap"
        return True, ""

    if "scalar" in low and "without" in low:
        if _max_consecutive_scale_steps(notes, key_center=key_center) >= 5:
            return False, "extended scalar run"
        return True, ""

    if "silence" in low or "rest" in low:
        syms = motif_rhythm_symbols(motif)
        if not any(s in ("z", "Z") for s in syms):
            return False, "missing rest"
        return True, ""

    if "pattern" in low and "twice" in low:
        rk = str(motif.get("rhythm_key") or "")
        if "|" not in rk:
            return False, "expected two rhythm cells"
        a, b = rk.split("|", 1)
        if a.strip() == b.strip():
            return False, "repeated rhythm cell"
        return True, ""

    if ("dominant" in low or "tension" in low) and classify_chord_quality(chord) == "dom":
        tones = chord_tone_names(chord, reference_key=key_center)
        if len(tones) >= 4 and tones[3].replace("b", "")[:1]:
            return True, ""
        return True, ""

    if "chromatic" in low and "approach" in low:
        allowed_pcs = set(_pitch_classes(chord_tone_names(chord, reference_key=key_center)))
        pcs_seq = _pitch_classes(notes)
        for a, b in zip(pcs_seq, pcs_seq[1:]):
            if b in allowed_pcs and min((a - b) % 12, (b - a) % 12) == 1:
                return True, ""
        return False, "no chromatic approach into a chord tone"

    if "enclose" in low or "enclosure" in low:
        allowed = _chord_tone_pcs(chord, key_center=key_center)
        if pcs & allowed:
            return True, ""
        return False, "line never touches a chord tone to resolve onto"

    if "3rd" in low and "resolve" in low:
        tones = chord_tone_names(chord, reference_key=key_center)
        third_pc = _pitch_classes([tones[1]])[0] if len(tones) >= 2 else None
        if third_pc is not None and _pitch_classes([notes[-1]])[0] == third_pc:
            return True, ""
        return False, "does not resolve to the 3rd"

    if "bebop" in low:
        allowed = _chord_tone_pcs(chord, key_center=key_center)
        if len(notes) >= 4 and len(pcs & allowed) >= 2:
            return True, ""
        return False, "not enough chord-tone grounding for a bebop line"

    if "pentatonic" in low:
        relationship = str(motif.get("pentatonic_relationship") or "").strip()
        if not relationship:
            # No stored tag (older/foreign example) - fall back to the same
            # rng-free default the generator itself uses for this quality.
            relationship = _pentatonic_relationship_for_quality(classify_chord_quality(chord))
        _proot, _kind, scale_notes, _label = resolve_pentatonic_choice(chord, key_center, relationship)
        allowed_pentatonic = set(_pitch_classes(scale_notes))
        if not pcs.issubset(allowed_pentatonic):
            return False, "note outside the chosen pentatonic collection"
        chord_pcs = _chord_tone_pcs(chord, key_center=key_center)
        if chord_pcs and not (pcs & chord_pcs):
            return False, "pentatonic line never touches a chord tone"
        return True, ""

    if "blues" in low:
        relationship = str(motif.get("pentatonic_relationship") or "").strip()
        if not relationship:
            relationship = _blues_relationship_for_quality(classify_chord_quality(chord))
        _proot, _kind, scale_notes, _label, _blue = resolve_blues_choice(chord, key_center, relationship)
        allowed_blues = set(_pitch_classes(scale_notes))
        if not pcs.issubset(allowed_blues):
            return False, "note outside the chosen blues collection"
        chord_pcs = _chord_tone_pcs(chord, key_center=key_center)
        if chord_pcs and not (pcs & chord_pcs):
            return False, "blues line never touches a chord tone"
        return True, ""

    if "syncopat" in low:
        allowed = _chord_tone_pcs(chord, key_center=key_center)
        try:
            _mode, scale_pcs = _parse_key_scale(key_center)
        except Exception:
            scale_pcs = ()
        allowed = allowed | set(scale_pcs)
        if allowed and not pcs.issubset(allowed):
            return False, "note outside the active harmonic context"
        families = list((motif.get("rhythm_meta") or {}).get("families") or [])
        if not ({"syncopated", "rest"} & set(families)):
            return False, "no syncopation (offbeat/rest) found in the rhythm"
        return True, ""

    return True, ""
