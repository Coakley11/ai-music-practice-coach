"""Capture Phase 2A AMI + Practice Focus evidence (no Streamlit import)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from music_coach_ami.pipeline import run_coach_pipeline
from practice_focus_coaching import practice_page_focus_lines, practice_page_watch_for
from practice_setup_globals import set_active_focus

OUT = Path(__file__).resolve().parent / "evidence-practice-focus"
SONG = "Shape of You"
CHORDS = {
    "first_chord": "Em",
    "second_chord": "C",
    "chord_path": "Em | C | G | D",
    "section_name": "Verse",
}


def _write(name: str, text: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(text.strip() + "\n", encoding="utf-8")
    print(f"wrote {name}", flush=True)


def _ami(instrument: str, focus: str, question: str, session: dict | None = None):
    ss = session if session is not None else {
        "instrument": instrument,
        "focus": focus,
        "level": "Intermediate",
    }
    ss.setdefault("instrument", instrument)
    ss.setdefault("focus", focus)
    ss.setdefault("level", "Intermediate")
    return run_coach_pipeline(
        question,
        ss,
        ami_ctx={
            "instrument": instrument,
            "focus": ss.get("focus") or focus,
            "level": "Intermediate",
            "active_song": {"title": SONG},
        },
    )


def _dump_ami(name: str, instrument: str, focus: str, question: str, session: dict | None = None) -> str:
    resp = _ami(instrument, focus, question, session=session)
    assert resp is not None
    body = [
        f"# {name}",
        f"Instrument: {instrument}",
        f"Practice Focus: {focus}",
        f"Question: {question}",
        f"Intent: {resp.intent}",
        "",
        resp.composed_markdown(),
        "",
        "## Practice steps",
        "\n".join(resp.practice_steps or []) or "(none)",
        "",
        f"diagnostics.practice_focus_not_applied={resp.diagnostics.get('practice_focus_not_applied')}",
        f"diagnostics.policy_plan={resp.diagnostics.get('policy_plan')}",
        f"diagnostics.focus_profile={resp.diagnostics.get('focus_profile')}",
    ]
    text = "\n".join(body)
    _write(name, text)
    return text


def _dump_page(name: str, instrument: str, focus: str) -> str:
    lines = practice_page_focus_lines(instrument, focus, **CHORDS)
    watch = practice_page_watch_for(instrument, focus)
    body = [
        f"# Practice page coaching — {instrument} / {focus}",
        "",
        "## Recommended drills",
        *[f"- {line}" for line in lines],
        "",
        "## What to listen / watch for",
        *[f"- {line}" for line in watch],
    ]
    text = "\n".join(body)
    _write(name, text)
    return text


def main() -> None:
    _dump_page("A-guitar-strumming-practice.txt", "Guitar", "Strumming")
    _dump_page("B-guitar-timing-practice.txt", "Guitar", "Timing")
    _dump_page("C-guitar-harmony-practice.txt", "Guitar", "Harmony")
    _dump_page("D-sax-tone-practice.txt", "Saxophone", "Tone")
    _dump_ami(
        "E-ami-guitar-strumming.txt",
        "Guitar",
        "Strumming",
        "What should I practice today?",
    )
    session = {"instrument": "Guitar", "focus": "Strumming", "level": "Intermediate"}
    _dump_ami(
        "F-ami-guitar-timing-same-rerun.txt",
        "Guitar",
        "Timing",
        "What should I practice today?",
        session=session,
    )
    set_active_focus(session, "Timing", source="evidence")
    # Re-capture after same-session focus change without restating focus in ami_ctx.
    resp = run_coach_pipeline(
        "What should I practice today?",
        session,
        ami_ctx={"instrument": "Guitar", "level": "Intermediate", "active_song": {"title": SONG}},
    )
    assert resp is not None
    _write(
        "F-ami-guitar-timing-after-set_active_focus.txt",
        "\n".join(
            [
                "# Same-rerun Timing after set_active_focus",
                f"session.focus={session.get('focus')}",
                "",
                resp.composed_markdown(),
            ]
        ),
    )
    _dump_ami(
        "G-ami-c-major-guardrail.txt",
        "Guitar",
        "Strumming",
        "What notes are in C major?",
    )
    _dump_ami(
        "H-ami-sax-tone.txt",
        "Saxophone",
        "Tone",
        "What should I practice today?",
    )
    _dump_ami(
        "H-ami-sax-articulation.txt",
        "Saxophone",
        "Articulation",
        "What should I practice today?",
    )
    _dump_ami(
        "H-ami-sax-phrasing.txt",
        "Saxophone",
        "Phrasing",
        "What should I practice today?",
    )
    _dump_ami(
        "I-ami-guitar-strumming-20min.txt",
        "Guitar",
        "Strumming",
        "Give me a 20-minute practice routine.",
    )
    _dump_ami(
        "I-ami-sax-tone-20min.txt",
        "Saxophone",
        "Tone",
        "Give me a 20-minute practice routine.",
    )
    _dump_page("J-sax-articulation-practice.txt", "Saxophone", "Articulation")
    _dump_page("J-sax-phrasing-practice.txt", "Saxophone", "Phrasing")
    print("done", flush=True)


if __name__ == "__main__":
    main()
