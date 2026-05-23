"""Time signature helpers for backing audio, timelines, and charts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

BACKING_TIME_SIGNATURES: tuple[str, ...] = ("4/4", "3/4", "6/8", "2/4", "12/8")


@dataclass(frozen=True)
class MeterTiming:
    time_signature: str
    pulses_per_bar: int
    pulse_sec: float
    bar_sec: float
    compound: bool


def parse_time_signature(time_signature: str) -> tuple[int, int]:
    raw = str(time_signature or "4/4").strip()
    if "/" not in raw:
        return 4, 4
    left, right = raw.split("/", 1)
    try:
        return max(1, int(left)), max(1, int(right))
    except ValueError:
        return 4, 4


def normalize_time_signature(time_signature: str) -> str:
    num, den = parse_time_signature(time_signature)
    label = f"{num}/{den}"
    return label if label in BACKING_TIME_SIGNATURES else "4/4"


def is_compound_meter(time_signature: str) -> bool:
    num, den = parse_time_signature(time_signature)
    return den == 8 and num % 3 == 0 and num >= 6


def meter_timing(bpm: int, time_signature: str) -> MeterTiming:
    """Timing grid for one chord bar (one notated measure)."""
    ts = normalize_time_signature(time_signature)
    num, den = parse_time_signature(ts)
    bpm = max(1, int(bpm))
    compound = is_compound_meter(ts)

    if compound:
        dotted_quarters = num // 3
        bar_sec = dotted_quarters * (60.0 / bpm)
        pulses = num
        pulse_sec = bar_sec / pulses
    else:
        pulses = num
        bar_sec = pulses * (60.0 / bpm)
        pulse_sec = bar_sec / pulses

    return MeterTiming(
        time_signature=ts,
        pulses_per_bar=pulses,
        pulse_sec=pulse_sec,
        bar_sec=bar_sec,
        compound=compound,
    )


def beats_per_bar_from_signature(time_signature: str) -> int:
    """Pulse count per bar (6 for 6/8, 4 for 4/4)."""
    return meter_timing(100, time_signature).pulses_per_bar


def metronome_accents(time_signature: str) -> list[int]:
    """1-based beat indices that receive the strong click."""
    ts = normalize_time_signature(time_signature)
    if ts == "6/8":
        return [1, 4]
    if ts == "12/8":
        return [1, 4, 7, 10]
    if ts == "3/8":
        return [1]
    return [1]


def default_time_signature_for_record(
    record: dict[str, Any] | None,
    sections: dict[str, list[str]] | None = None,
    *,
    song_title: str = "",
) -> str:
    record = record or {}
    ext = record.get("extensions") or {}
    if ext.get("time_signature"):
        return normalize_time_signature(str(ext["time_signature"]))
    if ext.get("default_time_signature"):
        return normalize_time_signature(str(ext["default_time_signature"]))

    title = (record.get("title") or song_title or "").lower()
    keys = " ".join((sections or {}).keys()).lower()
    text = f"{title} {keys}"
    if "3/4" in text or "piano man" in title:
        return "3/4"
    if "2/4" in text:
        return "2/4"
    if "12/8" in text:
        return "12/8"
    if "6/8" in text or "perfect" in title:
        return "6/8"
    return "4/4"
