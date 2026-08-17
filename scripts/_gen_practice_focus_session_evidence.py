"""Generate Phase 3A Practice Focus session / weakness evidence artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from practice_focus_coaching import build_focus_timed_session
from practice_focus_weaknesses import (
    audit_weakness_sources,
    format_adaptive_weakness_markdown,
    rank_measured_weaknesses,
)

OUT = Path(__file__).resolve().parent / "evidence-practice-focus-session"
OUT.mkdir(parents=True, exist_ok=True)

CASES = [
    ("guitar-strumming.txt", "Guitar", "Strumming"),
    ("guitar-timing.txt", "Guitar", "Timing"),
    ("guitar-harmony.txt", "Guitar", "Harmony"),
    ("sax-tone.txt", "Saxophone", "Tone"),
    ("sax-articulation.txt", "Saxophone", "Articulation"),
    ("sax-phrasing.txt", "Saxophone", "Phrasing"),
]


def main() -> None:
    for name, inst, focus in CASES:
        session = build_focus_timed_session(inst, focus, minutes=30, song="Demo Song")
        lines = [session["summary"], "", "Blocks:"]
        for block in session["blocks"]:
            lines.append(
                f"- {block['minutes']} min {block['name']}: {block['detail']}"
            )
        lines.append("")
        lines.append("Listen for: " + "; ".join(session["listen_for"][:3]))
        (OUT / name).write_text("\n".join(lines), encoding="utf-8")

    scores = {"timing": 20, "tone": 70, "groove": 55}
    (OUT / "weakness-tone-focus-severe-timing.txt").write_text(
        format_adaptive_weakness_markdown(
            "Saxophone", "Tone", song="Demo", scores=scores
        ),
        encoding="utf-8",
    )
    (OUT / "weakness-strumming-no-invention.txt").write_text(
        format_adaptive_weakness_markdown(
            "Guitar", "Strumming", song="Demo", scores={}
        ),
        encoding="utf-8",
    )
    (OUT / "audit-sources.json").write_text(
        json.dumps(audit_weakness_sources(), indent=2),
        encoding="utf-8",
    )
    (OUT / "rank-order.json").write_text(
        json.dumps(rank_measured_weaknesses(scores, "Saxophone", "Tone"), indent=2),
        encoding="utf-8",
    )
    print(f"wrote {len(list(OUT.iterdir()))} files to {OUT}")


if __name__ == "__main__":
    main()
