"""Tempo authority for Mission Recording coaching.

Three different tempos exist and must not be confused:

* **song reference tempo** — the catalog / original tempo of the song (context only);
* **Mission practice tempo** — the tempo the player deliberately chose for the Mission take; it is
  *sealed with the take* (the Mission's tempo when the recording was made), so changing the Mission
  afterwards never changes how an earlier take is coached;
* **detected performance tempo** — the pulse estimated from the audio.

For a Mission Recording the sealed Mission tempo is the target for timing coaching, practice ladders
and the next-practice recommendation. Without a Mission tempo (ordinary song analysis) nothing here
applies and the song reference keeps its role.
"""

from __future__ import annotations

from typing import Any

_FLOOR_BPM = 55
CLOSE_BPM = 3  # within this many BPM of the target counts as "on tempo"


def _as_bpm(value: Any) -> int | None:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def mission_tempo(ctx: dict[str, Any] | None) -> int | None:
    """The sealed Mission practice tempo of this take (None for ordinary song analysis)."""
    return _as_bpm((ctx or {}).get("mission_tempo_bpm"))


def song_reference_tempo(ctx: dict[str, Any] | None) -> int | None:
    ctx = ctx or {}
    ref = ctx.get("reference_bpm")
    return _as_bpm(ref if ref not in (None, "") else ctx.get("practice_bpm"))


def coaching_target_tempo(ctx: dict[str, Any] | None) -> int | None:
    """The tempo coaching is measured against: the Mission tempo, else the song reference."""
    return mission_tempo(ctx) or song_reference_tempo(ctx)


def practice_ladder(target: int) -> tuple[int, int, int]:
    """A short ladder that ends at the target: 90 % → 95 % → 100 %."""
    return (max(_FLOOR_BPM, int(round(target * 0.9))), max(_FLOOR_BPM, int(round(target * 0.95))), int(target))


def next_practice_tempo(target: int, timing_score: float | None, level: str = "") -> int:
    """Tempo for the next Mission attempt, derived from the Mission tempo, how the timing went and the
    player's level: strong timing keeps the Mission tempo, middling timing eases off 5 %, weak timing
    10 %; Beginner steps one tier easier."""
    if timing_score is None:
        tier = 0
    elif timing_score >= 80:
        tier = 0
    elif timing_score >= 65:
        tier = 1
    else:
        tier = 2
    if str(level or "").strip().lower().startswith("beginner"):
        tier = min(2, tier + 1)
    return max(_FLOOR_BPM, int(round(target * (1.0, 0.95, 0.9)[tier])))


def tempo_relation_sentence(detected: int, mission: int, reference: int | None, delta: int | None) -> str:
    """How the take's pulse relates to the Mission tempo (and, only as context, to the song reference).

    ``delta`` is detected − mission when both share a beat unit, else None (the caller has already
    explained the subdivision caution)."""
    if delta is None:
        return ""
    same_as_song = reference is None or abs(mission - reference) <= CLOSE_BPM
    if abs(delta) <= CLOSE_BPM:
        if same_as_song:
            tail = f" ({mission} BPM, also the song's reference tempo)" if reference else f" ({mission} BPM)"
            return f"Detected tempo ≈ {detected} BPM is near the Mission practice tempo{tail}."
        way = "faster" if mission > reference else "slower"
        return (f"Your detected pulse (~{detected} BPM) is very close to the Mission practice tempo ({mission} BPM). "
                f"The song's catalog reference is {reference} BPM, but this take was intentionally practiced {way}.")
    side = "above" if delta > 0 else "below"
    verdict = "fast" if delta > 0 else "slow"
    text = (f"Detected performance tempo ≈ {detected} BPM is {abs(delta)} BPM {side} the Mission practice tempo "
            f"({mission} BPM) — {verdict} relative to the Mission target of {mission} BPM.")
    if reference and not same_as_song:
        text += f" (The song's catalog reference of {reference} BPM is context only.)"
    return text


__all__ = [
    "CLOSE_BPM",
    "coaching_target_tempo",
    "mission_tempo",
    "next_practice_tempo",
    "practice_ladder",
    "song_reference_tempo",
    "tempo_relation_sentence",
]
