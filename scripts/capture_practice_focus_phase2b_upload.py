"""Capture Phase 2B Upload / AI Coach Practice Focus evidence (no Streamlit app import)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from practice_focus_evaluation import (
    apply_focus_to_coach_outputs,
    compact_analysis_focus_block,
    prepare_upload_analysis_context,
    stamp_result_with_frozen_snapshot,
)
from practice_setup_globals import set_active_focus
from recording_analysis_ui import render_analysis_dashboard
from upload_history import compact_analysis_for_history

OUT = Path(__file__).resolve().parent / "evidence-practice-focus-upload"


def _write(name: str, text: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(text.strip() + "\n", encoding="utf-8")
    print(f"wrote {name}", flush=True)


def _scores(**overrides: int) -> dict[str, int]:
    base = {
        "timing": 61,
        "pitch": 74,
        "technique": 67,
        "groove": 58,
        "musicality": 70,
        "confidence": 66,
        "tone": 72,
    }
    base.update(overrides)
    return base


def _result(instrument: str, focus: str, scores: dict, *, timing_severe: bool = False) -> dict:
    session = {"instrument": instrument, "focus": focus, "level": "Intermediate"}
    ctx = {"instrument": instrument, "focus": focus, "mission_ids": ["motif_development"]}
    prepare_upload_analysis_context(session, ctx)
    if timing_severe:
        scores = dict(scores)
        scores["timing"] = 34
    cats = {
        "timing": {
            "findings": ["Onsets drift from the beat into phrase peaks."],
            "tips": ["Count the subdivision, then loop a short passage."],
        },
        "groove": {
            "findings": ["Attack consistency wobbles through chord changes."],
            "tips": ["Mute strings and keep the hand moving."],
        },
        "tone": {
            "findings": [f"Spectral centroid average is available; voiced ratio is supportable."],
            "tips": ["Match tone quality across a short phrase."],
        },
        "pitch": {"findings": ["Pitch track is usable."], "tips": []},
    }
    focused = apply_focus_to_coach_outputs(
        scores=scores,
        categories=cats,
        practice_plan=["C major scale @ 70 BPM — even subdivisions."],
        instrument=instrument,
        focus=focus,
        baseline_summary="Pulse, pitch, dynamics, and attack clarity were estimated from this take.",
        biggest_issue=cats["timing"]["findings"][0],
        most_improved="Pitch — score 74/100",
        next_focus=cats["groove"]["tips"][0],
    )
    payload = {
        "ok": True,
        "instrument": instrument,
        "scores": scores,
        "categories": cats,
        "coach_summary": focused["coach_summary"],
        "practice_plan": focused["practice_plan"],
        "biggest_issue": focused["biggest_issue"],
        "most_improved": focused["most_improved"],
        "next_focus": focused["next_focus"],
        "mission_ids": ctx.get("mission_ids"),
    }
    stamped = stamp_result_with_frozen_snapshot(payload, ctx.get("practice_focus_snapshot"))
    stamped["practice_focus_analysis_block"] = compact_analysis_focus_block(instrument, focus)
    return stamped, session, ctx


def _dump(name: str, result: dict) -> None:
    body = [
        f"# {name}",
        f"Practice Focus at analysis: {result.get('practice_focus_at_analysis')}",
        f"instrument: {result.get('instrument')}",
        f"mission_ids: {result.get('mission_ids')}",
        "",
        "## Coach summary",
        str(result.get("coach_summary") or ""),
        "",
        "## Next practice",
        "\n".join(f"- {p}" for p in (result.get("practice_plan") or [])),
        "",
        "## Compact analysis block",
        str(result.get("practice_focus_analysis_block") or ""),
    ]
    _write(f"{name}.txt", "\n".join(body))
    html = render_analysis_dashboard(result)
    (OUT / f"{name}.html").write_text(html, encoding="utf-8")
    print(f"wrote {name}.html", flush=True)


def main() -> None:
    scores = _scores()
    strum, session, _ctx = _result("Guitar", "Strumming", scores)
    _dump("A-guitar-strumming-upload", strum)

    set_active_focus(session, "Timing", source="evidence")
    timing, _s2, _c2 = _result("Guitar", "Timing", scores)
    _dump("B-guitar-timing-upload", timing)

    tone, _s3, _c3 = _result("Saxophone", "Tone", scores)
    _dump("C-sax-tone-upload", tone)

    set_active_focus(session, "Harmony", source="evidence")
    compact = compact_analysis_for_history(strum)
    _write(
        "D-historical-strumming-after-harmony.txt",
        "\n".join(
            [
                "# Historical immutability",
                f"current session focus after change: {session.get('focus')}",
                f"saved practice_focus_at_analysis: {compact.get('practice_focus_at_analysis')}",
                f"snapshot: {compact.get('practice_focus_snapshot')}",
            ]
        ),
    )

    harmony, _s4, _c4 = _result("Guitar", "Harmony", scores)
    _dump("E-guitar-harmony-new-analysis", harmony)
    _write(
        "E-coexistence.txt",
        "\n".join(
            [
                f"old: {compact.get('practice_focus_at_analysis')}",
                f"new: {harmony.get('practice_focus_at_analysis')}",
            ]
        ),
    )

    guard, _s5, _c5 = _result("Saxophone", "Tone", scores, timing_severe=True)
    _dump("F-tone-focus-severe-timing", guard)
    print("done", flush=True)


if __name__ == "__main__":
    main()
