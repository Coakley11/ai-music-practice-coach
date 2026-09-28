# -*- coding: utf-8 -*-
"""Compare Mobile M5 before/after fold metrics."""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "evidence-mobile-m5"


def h(obj, *path):
    cur = obj
    for p in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    if isinstance(cur, dict) and "h" in cur:
        return cur["h"]
    return cur


def main() -> int:
    before = json.loads((OUT / "m5_before_metrics.json").read_text(encoding="utf-8"))
    after = json.loads((OUT / "m5_after_metrics.json").read_text(encoding="utf-8"))
    rows = []
    for vp in ("360", "390", "430", "1280"):
        for page in ("practice", "backing", "creative"):
            b = before["viewports"][vp][page]
            a = after["viewports"][vp][page]
            b_scroll = b.get("mainScrollH")
            a_scroll = a.get("mainScrollH")
            delta = None if b_scroll is None or a_scroll is None else a_scroll - b_scroll
            pct = None if not b_scroll else round(100.0 * (a_scroll - b_scroll) / b_scroll, 1)
            rows.append(
                {
                    "vp": vp,
                    "page": page,
                    "before_scrollH": b_scroll,
                    "after_scrollH": a_scroll,
                    "delta_px": delta,
                    "delta_pct": pct,
                    "before_headerH": h(b, "scriptHeader"),
                    "after_headerH": h(a, "scriptHeader"),
                    "before_practiceH": h(b, "practicePanel"),
                    "after_practiceH": h(a, "practicePanel"),
                    "before_backingH": h(b, "backingPanel"),
                    "after_backingH": h(a, "backingPanel"),
                    "before_creativeH": h(b, "creativePanel"),
                    "after_creativeH": h(a, "creativePanel"),
                    "before_m5": b.get("m5"),
                    "after_m5": a.get("m5"),
                    "before_advOpen": b.get("advancedOpen"),
                    "after_advOpen": a.get("advancedOpen"),
                }
            )
    summary = {"rows": rows}
    (OUT / "m5_before_after_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    # Phone pages should not grow; desktop scroll should be ~unchanged (±5%).
    for row in rows:
        if row["vp"] == "1280":
            if row["before_scrollH"] and row["after_scrollH"]:
                assert abs(row["delta_pct"] or 0) <= 8, row
            assert not row["after_m5"], row
        else:
            assert row["after_m5"] == "m5-fold-density-v1", row
            if row["before_scrollH"] and row["after_scrollH"]:
                assert row["after_scrollH"] <= row["before_scrollH"] + 40, row
    print("COMPARE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
