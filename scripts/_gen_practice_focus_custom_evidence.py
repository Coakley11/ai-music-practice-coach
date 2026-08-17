"""Generate Phase 3B Custom / Arrangement Focus evidence artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creative_lab_text import creativity_arrangement_text
from custom_progression_lab import generate_exercises_markdown

OUT = Path(__file__).resolve().parent / "evidence-practice-focus-custom"
OUT.mkdir(parents=True, exist_ok=True)

SECTIONS = {
    "Verse": [
        {"chord": "G", "bars": 1},
        {"chord": "D", "bars": 1},
        {"chord": "Em", "bars": 1},
        {"chord": "C", "bars": 1},
    ],
}


def _md(instrument: str, focus: str, *, user_request: str = "") -> str:
    return generate_exercises_markdown(
        sections=SECTIONS,
        instrument=instrument,
        level="Intermediate",
        focus=focus,
        key_center="G",
        groove_style="Pop",
        time_signature="4/4",
        bpm=100,
        user_request=user_request,
    )


def main() -> None:
    cases = [
        ("custom-guitar-strumming.txt", "Guitar", "Strumming", ""),
        ("custom-guitar-timing.txt", "Guitar", "Timing", ""),
        ("custom-guitar-harmony.txt", "Guitar", "Harmony", ""),
        ("custom-sax-tone.txt", "Saxophone", "Tone", ""),
        ("custom-sax-articulation.txt", "Saxophone", "Articulation", ""),
        ("custom-sax-phrasing.txt", "Saxophone", "Phrasing", ""),
        (
            "custom-explicit-chord-tones-under-strumming.txt",
            "Guitar",
            "Strumming",
            "Give me a chord-tone exercise over G-D-Em-C.",
        ),
        ("custom-unknown-focus.txt", "Piano", "My Weird Custom Focus XYZ", ""),
    ]
    for name, inst, focus, req in cases:
        (OUT / name).write_text(_md(inst, focus, user_request=req), encoding="utf-8")

    ctx = {
        "song": "Demo Song",
        "instrument": "Guitar",
        "level": "Intermediate",
        "focus": "Harmony",
        "genre": "Pop",
        "sections": {"Verse": ["G", "D", "Em", "C"]},
        "chart_key": "G",
        "display_key": "G",
        "key": "G",
    }
    for focus, fname in (
        ("Harmony", "arrangement-harmony.txt"),
        ("Melody", "arrangement-melody.txt"),
        ("Timing", "arrangement-timing.txt"),
        ("Phrasing", "arrangement-phrasing.txt"),
    ):
        text = creativity_arrangement_text({**ctx, "focus": focus}, "Pop Rock", "Verse")
        (OUT / fname).write_text(text, encoding="utf-8")

    same_rerun = (
        "=== Strumming ===\n"
        + _md("Guitar", "Strumming")
        + "\n\n=== After Focus → Harmony (same progression) ===\n"
        + _md("Guitar", "Harmony")
    )
    (OUT / "custom-same-rerun-strumming-to-harmony.txt").write_text(
        same_rerun, encoding="utf-8"
    )
    print(f"wrote {len(list(OUT.iterdir()))} files to {OUT}")


if __name__ == "__main__":
    main()
