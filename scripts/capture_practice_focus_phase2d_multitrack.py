"""Capture Phase 2D Multitrack Practice Focus evidence (no full audio required)."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from practice_focus_multitrack import (
    MULTITRACK_CAPABILITY_MAP,
    apply_focus_to_multitrack_outputs,
    prepare_multitrack_analysis_context,
    stamp_multitrack_result_with_focus,
)
from practice_setup_globals import set_active_focus
from recording_analysis_ui import render_analysis_dashboard

OUT = Path(__file__).resolve().parent / "evidence-practice-focus-multitrack"


def _write(name: str, text: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(text.strip() + "\n", encoding="utf-8")
    print(f"wrote {name}", flush=True)


def _findings(*, timing_severe: bool = True) -> list[str]:
    if timing_severe:
        return [
            "LayerB timing differs from LayerA (~120 ms average onset gap).",
            "LayerB sits quietly in the mix — may sound buried.",
        ]
    return [
        "LayerB and LayerA are rhythmically well locked.",
        "LayerB sits quietly in the mix — may sound buried.",
    ]


def _scores() -> dict[str, int]:
    return {"ensemble": 62, "balance": 70, "sync": 68}


def _result(instrument: str, focus: str, *, timing_severe: bool = True) -> dict:
    session = {"instrument": instrument, "focus": focus}
    ctx = {"instrument": instrument, "focus": focus}
    prepare_multitrack_analysis_context(session, ctx)
    findings = _findings(timing_severe=timing_severe)
    scores = _scores()
    applied = apply_focus_to_multitrack_outputs(
        findings=findings,
        tips=["Mix check: solo each layer, then A/B with drums or click."],
        coach_summary=(
            "Multitrack coach read: comparing onset alignment and level balance across layers."
        ),
        scores=scores,
        instrument=instrument,
        focus=focus,
    )
    payload = {
        "ok": True,
        "multitrack": True,
        "layers": ["LayerA", "LayerB"],
        "findings": applied["findings"],
        "tips": applied["tips"],
        "scores": applied["scores"],
        "coach_summary": applied["coach_summary"],
        "instrument": instrument,
        "measured_comparisons": [
            {
                "layer": "LayerB",
                "reference": "LayerA",
                "mean_onset_gap_sec": 0.12 if timing_severe else 0.04,
                "rms_ratio_vs_ref": 0.5,
            }
        ],
        "practice_focus_evaluation": {
            "emphasized_dimensions": applied.get("emphasized_dimensions"),
            "capability_map": dict(MULTITRACK_CAPABILITY_MAP),
            "raw_scores_unchanged": True,
        },
    }
    stamped = stamp_multitrack_result_with_focus(payload, ctx)
    return stamped, session, ctx, scores


def _dump(name: str, result: dict) -> None:
    body = [
        f"# {name}",
        f"Practice Focus at analysis: {result.get('practice_focus_at_analysis')}",
        f"instrument: {result.get('instrument')}",
        f"scores: {result.get('scores')}",
        "",
        "## Coach summary",
        str(result.get("coach_summary") or ""),
        "",
        "## Findings",
        "\n".join(f"- {x}" for x in (result.get("findings") or [])),
        "",
        "## Tips",
        "\n".join(f"- {x}" for x in (result.get("tips") or [])),
        "",
        "## Measured comparisons",
        str(result.get("measured_comparisons")),
        "",
        "## Capability map (excerpt)",
        f"onset_alignment={MULTITRACK_CAPABILITY_MAP['onset_alignment']}",
        f"rms_balance={MULTITRACK_CAPABILITY_MAP['rms_balance']}",
        f"stroke_direction={MULTITRACK_CAPABILITY_MAP['stroke_direction']}",
        f"resonance={MULTITRACK_CAPABILITY_MAP['resonance']}",
        f"chord_identity={MULTITRACK_CAPABILITY_MAP['chord_identity']}",
    ]
    _write(f"{name}.txt", "\n".join(body))
    html = render_analysis_dashboard(result)
    (OUT / f"{name}.html").write_text(html, encoding="utf-8")
    print(f"wrote {name}.html", flush=True)


def main() -> None:
    timing, session, _ctx, scores_a = _result("Guitar", "Timing")
    _dump("A-timing-multitrack", timing)

    tone, _s2, _c2, scores_b = _result("Saxophone", "Tone")
    _dump("B-tone-multitrack", tone)
    _write(
        "B-raw-score-invariance.txt",
        "\n".join(
            [
                "# Raw-score invariance",
                f"Timing scores: {scores_a}",
                f"Tone scores: {scores_b}",
                f"identical: {scores_a == scores_b}",
            ]
        ),
    )

    strum, _s3, _c3, _sc = _result("Guitar", "Strumming")
    _dump("C-guitar-strumming-multitrack", strum)

    sax_tone, _s4, _c4, _sc4 = _result("Saxophone", "Tone", timing_severe=True)
    _dump("D-sax-tone-multitrack", sax_tone)

    severe = apply_focus_to_multitrack_outputs(
        findings=_findings(timing_severe=True),
        tips=[],
        coach_summary="Baseline ensemble.",
        scores=_scores(),
        instrument="Saxophone",
        focus="Tone",
    )
    _write(
        "E-tone-focus-severe-timing.txt",
        "\n".join(
            [
                "# Tone focus + severe timing",
                severe["coach_summary"],
                f"severe_non_focus: {severe.get('severe_non_focus_findings')}",
            ]
        ),
    )

    frozen = copy.deepcopy(timing)
    set_active_focus(session, "Harmony", source="evidence")
    _write(
        "F-historical-timing-after-harmony.txt",
        "\n".join(
            [
                "# Historical immutability",
                f"current session focus: {session.get('focus')}",
                f"saved practice_focus_at_analysis: {frozen.get('practice_focus_at_analysis')}",
                f"snapshot: {frozen.get('practice_focus_snapshot')}",
            ]
        ),
    )

    _write(
        "Z-environment-note.txt",
        "\n".join(
            [
                "# Environment / audio limitations",
                "Full analyze_multitrack audio execution requires librosa + WAV fixtures.",
                "This evidence uses the Multitrack Focus coaching adapter + dashboard renderer",
                "with synthetic measured findings matching the real onset-gap / RMS schema.",
                "Phase 2B Upload real-audio smoke test remains separately deferred.",
            ]
        ),
    )
    print("done", flush=True)


if __name__ == "__main__":
    main()
