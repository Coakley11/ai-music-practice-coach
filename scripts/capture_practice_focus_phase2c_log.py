"""Capture Phase 2C Practice Log / Practice Coach Focus evidence (no Streamlit app import)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from practice_focus_history import (
    aggregate_practice_focus_history,
    compact_practice_focus_coach_block,
    log_entry_focus_caption,
)
from practice_history_synthesis import (
    build_practice_log_ami_summary,
    build_practice_progress_report,
    format_progress_report_markdown,
)
from practice_log_state import build_practice_log_prefill, migrate_practice_log_entry
from practice_setup_globals import set_active_focus

OUT = Path(__file__).resolve().parent / "evidence-practice-focus-log"


def _write(name: str, text: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(text.strip() + "\n", encoding="utf-8")
    print(f"wrote {name}", flush=True)


def _make(session: dict, *, minutes: int, notes: str = "", hard: str = "", day: str = "2026-08-10") -> dict:
    prefill = build_practice_log_prefill(session)
    return migrate_practice_log_entry(
        {
            **prefill,
            "session_id": f"{session.get('focus')}-{day}-{minutes}",
            "date": day,
            "duration_minutes": minutes,
            "notes": notes,
            "what_was_hard": hard,
            "active_song": "Autumn Leaves",
        }
    )


def main() -> None:
    sax = {"instrument": "Saxophone", "focus": "Tone", "level": "Intermediate"}
    tone_entry = _make(
        sax,
        minutes=20,
        notes="Long tones + scale work",
        hard="tone became thinner in upper register",
        day="2026-08-10",
    )
    _write(
        "A-sax-tone-log-card.txt",
        "\n".join(
            [
                "# A Sax Tone historical entry",
                log_entry_focus_caption(tone_entry),
                f"focus={tone_entry.get('focus')}",
                f"focus_area={tone_entry.get('focus_area')}",
                f"snapshot={tone_entry.get('practice_focus_snapshot')}",
            ]
        ),
    )

    set_active_focus(sax, "Articulation", source="evidence")
    _write(
        "A-sax-tone-after-articulation-change.txt",
        "\n".join(
            [
                "# After current Focus → Articulation",
                f"current session focus: {sax.get('focus')}",
                f"saved caption: {log_entry_focus_caption(tone_entry)}",
                f"saved focus: {tone_entry.get('focus')}",
            ]
        ),
    )

    set_active_focus(sax, "Phrasing", source="evidence")
    phrasing = _make(sax, minutes=15, notes="phrase shapes", day="2026-08-11")
    _write(
        "B-same-rerun-phrasing.txt",
        "\n".join(
            [
                "# Same-rerun new entry",
                f"current focus at save: {sax.get('focus')}",
                log_entry_focus_caption(phrasing),
                f"snapshot focus: {(phrasing.get('practice_focus_snapshot') or {}).get('practice_focus')}",
            ]
        ),
    )

    guitar = {"instrument": "Guitar", "focus": "Strumming", "level": "Intermediate"}
    strum = _make(
        guitar,
        minutes=25,
        notes="lost groove during chord changes",
        hard="hand stops on transitions",
        day="2026-08-12",
    )
    _write(
        "C-guitar-strumming-log.txt",
        "\n".join(
            [
                "# Guitar Strumming",
                log_entry_focus_caption(strum),
                f"exact={strum.get('focus')}",
                f"coarse={strum.get('focus_area')}",
            ]
        ),
    )

    art = {"instrument": "Saxophone", "focus": "Articulation", "level": "Intermediate"}
    art_entry = _make(art, minutes=20, notes="tonguing exercise", day="2026-08-13")
    rows = [tone_entry, phrasing, strum, art_entry]
    # Rebuild tone with Articulation current for weekly analysis
    summary = build_practice_log_ami_summary(
        rows,
        window_days=0,
        current_focus="Articulation",
        current_instrument="Saxophone",
    )
    hist = summary.get("practice_focus_history") or {}
    block = compact_practice_focus_coach_block(hist)
    payload = {
        "practice_log_summary": summary,
        "practice_focus_history": hist,
        "practice_focus_history_block": block,
        "current_practice_focus": "Articulation",
        "upload_analysis_summary": {},
        "tone_history_summary": {},
        "multitrack_export_summary": {},
        "safety_checks": {"raw_audio_excluded": True, "base64_excluded": True},
    }
    report = build_practice_progress_report(payload)
    md = format_progress_report_markdown(report)
    _write(
        "D-mixed-week-aggregation.txt",
        "\n".join(
            [
                "# Mixed week Focus aggregation",
                f"exact counts: {hist.get('exact_focus_session_counts')}",
                f"minutes: {hist.get('exact_focus_recorded_minutes')}",
                f"pairs: {hist.get('instrument_focus_session_counts')}",
                f"dominant: {hist.get('dominant_exact_focus')}",
                "",
                block,
            ]
        ),
    )
    _write("E-practice-coach-report.md", md)
    _write(
        "E-current-vs-historical.txt",
        "\n".join(
            [
                "# Current vs historical",
                f"dominant historical: {hist.get('dominant_exact_focus')}",
                f"current: {hist.get('current_practice_focus')}",
                f"differs: {hist.get('current_differs_from_historical')}",
                "activity:",
                *[f"- {x}" for x in (report.get("practice_activity") or [])],
            ]
        ),
    )

    old = migrate_practice_log_entry(
        {
            "session_id": "legacy-missing",
            "instrument": "Saxophone",
            "notes": "old row without focus",
            "duration_minutes": 15,
            "date": "2026-07-01",
        }
    )
    _write(
        "F-old-missing-focus.txt",
        "\n".join(
            [
                "# Old missing Focus",
                log_entry_focus_caption(old),
                f"focus field: {old.get('focus')!r}",
                f"has snapshot: {bool(old.get('practice_focus_snapshot'))}",
                f"current selector ignored: Articulation",
            ]
        ),
    )
    print("done", flush=True)


if __name__ == "__main__":
    main()
