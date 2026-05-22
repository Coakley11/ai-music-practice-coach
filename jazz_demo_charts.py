"""Jazz-standard demo chart data (Blue Bossa, Take The A Train)."""

from __future__ import annotations

from typing import Any

_CPL_SECTIONS = [
    "Intro",
    "Verse",
    "Pre-Chorus",
    "Chorus",
    "Bridge",
    "Solo",
    "Outro",
]


def _e(chord: str, bars: int = 1) -> dict:
    return {"chord": chord, "bars": max(1, int(bars))}


def _r(bars: int = 1) -> dict:
    return {"repeat": True, "bars": max(1, int(bars))}


# Blue Bossa — Section A (Cm)
BLUE_BOSSA_SECTION_A: list[dict] = [
    _e("Cm7"),
    _r(),
    _e("Fm7"),
    _r(),
    _e("Dm7b5"),
    _e("G7b9"),
    _e("Cm7"),
    _r(),
    _e("Ebm7"),
    _e("Ab7"),
    _e("Dbmaj7"),
    _r(),
    _e("Dm7b5"),
    _e("G7b9"),
    _e("Cm7"),
    _e("Dm7b5"),
    _e("G7b9"),
]

# Take The A Train — A / B (C)
TAKE_THE_A_TRAIN_A: list[dict] = [
    _e("C6"),
    _r(),
    _e("D7#11"),
    _r(),
    _e("Dm7"),
    _e("G7"),
    _e("C6"),
    _e("Dm7"),
    _e("G7"),
]

TAKE_THE_A_TRAIN_B: list[dict] = [
    _e("Fmaj7"),
    _r(),
    _r(),
    _r(),
    _e("D7"),
    _r(),
    _e("Dm7"),
    _e("G7"),
    _e("G7b9"),
]

CPL_DEMO_CHARTS: dict[str, dict[str, Any]] = {
    "blue_bossa": {
        "name": "Blue Bossa",
        "progression_style": "Bossa",
        "original_key_center": "Cm",
        "time_signature": "4/4",
        "bpm": 120,
        "groove_style": "Bossa nova",
        "loops": 2,
        "section_labels": {"Verse": "A"},
        "original_sections": {
            "Verse": BLUE_BOSSA_SECTION_A,
        },
    },
    "take_the_a_train": {
        "name": "Take The A Train",
        "progression_style": "Jazz",
        "original_key_center": "C",
        "time_signature": "4/4",
        "bpm": 132,
        "groove_style": "Jazz swing",
        "loops": 2,
        "section_labels": {"Verse": "A", "Chorus": "B", "Bridge": "A"},
        "original_sections": {
            "Verse": TAKE_THE_A_TRAIN_A,
            "Chorus": TAKE_THE_A_TRAIN_B,
            "Bridge": TAKE_THE_A_TRAIN_A,
        },
    },
}

CPL_DEMO_PRESET_BY_STYLE: dict[str, dict[str, str]] = {
    "Bossa": {"Blue Bossa (jazz chart)": "blue_bossa"},
    "Jazz": {"Take The A Train (jazz chart)": "take_the_a_train"},
}


def build_demo_progression(demo_id: str) -> dict:
    """Full active progression dict for session state."""
    spec = CPL_DEMO_CHARTS.get(demo_id)
    if not spec:
        return {
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {n: [] for n in _CPL_SECTIONS},
            "progression_style": "Pop",
            "time_signature": "4/4",
            "bpm": 100,
            "groove_style": "Auto",
            "loops": 2,
            "user_locked_home_key": False,
        }
    sections = {n: [] for n in _CPL_SECTIONS}
    for name, entries in (spec.get("original_sections") or {}).items():
        if name in sections and entries:
            sections[name] = [dict(e) for e in entries]
    return {
        "name": spec.get("name", "My Progression"),
        "original_key_center": spec.get("original_key_center", "C"),
        "original_sections": sections,
        "progression_style": spec.get("progression_style", "Pop"),
        "time_signature": spec.get("time_signature", "4/4"),
        "bpm": int(spec.get("bpm", 100) or 100),
        "groove_style": spec.get("groove_style", "Auto"),
        "loops": int(spec.get("loops", 2) or 2),
        "section_labels": dict(spec.get("section_labels") or {}),
        "demo_chart_id": demo_id,
        "user_locked_home_key": True,
    }


def demo_presets_for_style(style: str) -> dict[str, str]:
    return dict(CPL_DEMO_PRESET_BY_STYLE.get(style, {}))
