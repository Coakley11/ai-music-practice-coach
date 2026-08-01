"""Mission hard constraints — validate phrases before display."""

from __future__ import annotations

from typing import Any

from music_theory import classify_chord_quality, normalize_root, split_chord
from improvisation_mission_rules import _chord_tone_pcs, _guide_third_seventh
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

    return True, ""
