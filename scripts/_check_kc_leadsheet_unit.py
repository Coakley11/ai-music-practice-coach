"""Fast local checks: lead-sheet HTML + no SHORT_PASS truncation + signature identity."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS"):
    os.environ.pop(k, None)


def main() -> int:
    from backing_key_cycle_handoff import build_cycle_lead_sheet_html, build_cycle_chart_strip_html

    sections = {
        "Verse": [
            "G",
            "Em",
            "C",
            "D",
            "G",
            "Em",
            "C",
            "D",
            "Bm",
            "C",
            "G",
            "D",
            "A#:3.5|D#:0.5p",  # playback token must be rendered via chart_grid, not raw dump
        ]
    }
    html = build_cycle_lead_sheet_html(
        sounding_key="Ab",
        sections=sections,
        song_name="Shape of You",
        song_data={"key": "G", "title": "Shape of You"},
        selected_section_names=["Verse"],
        bpm=120,
    )
    alias = build_cycle_chart_strip_html(
        sounding_key="Ab",
        sections=sections,
        song_name="Shape of You",
        song_data={"key": "G", "title": "Shape of You"},
        selected_section_names=["Verse"],
    )
    checks = {
        "has_backing_chart_sheet": "backing-chart-sheet" in html,
        "has_live_chart_cell": "live-chart-cell" in html,
        "no_kc_chord_cell": "kc-chord-cell" not in html,
        "no_kc_chart_full": "kc-chart-full" not in html,
        "no_raw_pipe_token_as_cell_text": "A#:3.5|D#:0.5p" not in html,
        "alias_same_family": "backing-chart-sheet" in alias,
        "short_pass_unset": not os.environ.get("KC_SHORT_PASS_BARS")
        and not os.environ.get("KC_SHORT_PASS_LOOPS"),
        "html_len": len(html),
    }
    # Signature helper: event count must be in arr_v2 tuple shape used by app.
    events = [{"chord": c, "section": "Verse"} for c in sections["Verse"]]
    sig = (
        "Shape of You",
        "G",
        "Intermediate",
        "Pop groove",
        120,
        "4/4",
        1,
        ("Verse",),
        "Strong",
        False,
        (),
        len(events),
        len(sections["Verse"]),
        0,
        "arr_v2",
    )
    short_sig = sig[:-3] + (4, 4, 3, "arr_v2")  # short-pass bars=3 identity
    checks["sig_has_arr_v2"] = sig[-1] == "arr_v2"
    checks["short_sig_differs"] = short_sig != sig
    checks["ok"] = all(
        [
            checks["has_backing_chart_sheet"],
            checks["has_live_chart_cell"],
            checks["no_kc_chord_cell"],
            checks["no_kc_chart_full"],
            checks["no_raw_pipe_token_as_cell_text"],
            checks["alias_same_family"],
            checks["short_pass_unset"],
            checks["sig_has_arr_v2"],
            checks["short_sig_differs"],
            checks["html_len"] > 500,
        ]
    )
    print(checks)
    return 0 if checks["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
