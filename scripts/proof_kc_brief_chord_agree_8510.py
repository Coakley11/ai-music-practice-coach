"""Brief: after Manual Next + one natural handoff, audible/Current/Next/sheet agree (8510)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from proof_kc_finish_five_8510 import clear_pause_hold, wait_idle  # noqa: E402
from proof_kc_focused_shared_8510 import (  # noqa: E402
    boot_cycle_verse,
    click_cycle_next,
    full_sync_probe,
    play_until_audible,
    save_report,
    sounding,
    wait_key_change,
    wait_playing,
)
from proof_kc_stop_resume_sequence_8510 import open_sheet  # noqa: E402
from proof_key_cycle_ux_8510 import cycle_ui, set_cycle_mode  # noqa: E402


def _agree(probe: dict) -> dict:
    buf = str(probe.get("bufKey") or "").strip()
    last = str(probe.get("lastKey") or probe.get("sounding") or "").strip()
    ui_c = str(probe.get("uiChord") or "").strip()
    ui_n = str(probe.get("uiNext") or "").strip()
    tl_c = str(probe.get("timelineChord") or "").strip()
    tl_n = str(probe.get("timelineNext") or "").strip()
    hi = str(probe.get("highlight") or "").strip()
    key_ok = bool(buf) and buf == last
    chord_ok = bool(probe.get("chordMatch")) and bool(ui_c or tl_c)
    next_ok = bool(probe.get("nextMatch")) and bool(ui_n or tl_n or ui_n == "—" or tl_n == "—")
    # Highlight may be "Bar N" chrome; prefer chord-symbol match when present.
    hi_ok = (not hi) or hi.lower().startswith("bar") or (
        ui_c and (hi == ui_c or ui_c.startswith(hi) or hi.startswith(ui_c))
    ) or (
        tl_c and (hi == tl_c or tl_c.startswith(hi) or hi.startswith(tl_c))
    )
    return {
        "ok": bool(key_ok and chord_ok and next_ok and hi_ok),
        "bufKey": buf,
        "sounding": last,
        "uiChord": ui_c,
        "uiNext": ui_n,
        "timelineChord": tl_c,
        "timelineNext": tl_n,
        "highlight": hi,
        "chordMatch": bool(probe.get("chordMatch")),
        "nextMatch": bool(probe.get("nextMatch")),
        "section": probe.get("uiSection") or probe.get("eventSection"),
        "t": probe.get("t"),
        "dur": probe.get("dur"),
        "tlLen": probe.get("tlLen"),
    }


def main() -> int:
    report: dict = {"proof": "brief_chord_agree_after_next", "checks": {}, "ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            boot_cycle_verse(page)
            play_until_audible(page)
            clear_pause_hold(page)
            open_sheet(page)
            wait_idle(page)

            key0 = sounding(page)
            ui = cycle_ui(page) or {}
            seq = ui.get("sequence") or ui.get("keys") or []
            if isinstance(seq, str):
                seq = [s.strip() for s in seq.split(",") if s.strip()]
            else:
                seq = [str(s) for s in seq]
            report["sequence"] = seq
            report["before_next"] = key0

            click_cycle_next(page)
            wait_idle(page, 20000)
            key1 = wait_key_change(page, key0, 90)
            wait_playing(page, 40)
            t_settle = time.time()
            after_next = full_sync_probe(page)
            while time.time() - t_settle < 45:
                after_next = full_sync_probe(page)
                c_try = _agree(after_next)
                if (
                    str(after_next.get("bufKey") or "") == key1
                    and float(after_next.get("dur") or 0) > 2
                    and c_try["ok"]
                ):
                    break
                page.wait_for_timeout(400)
            c1 = _agree(after_next)
            c1["key"] = key1
            report["checks"]["after_manual_next"] = c1
            print(
                f"after_next key={key1} buf={c1['bufKey']} "
                f"cur={c1['uiChord']}/{c1['timelineChord']} "
                f"next={c1['uiNext']}/{c1['timelineNext']} "
                f"match={c1['chordMatch']}/{c1['nextMatch']} ok={c1['ok']}",
                flush=True,
            )
            if not c1["ok"]:
                raise RuntimeError(f"disagree after Manual Next: {c1}")

            key2 = wait_key_change(page, key1, 180)
            t_settle = time.time()
            after_nat = full_sync_probe(page)
            while time.time() - t_settle < 45:
                after_nat = full_sync_probe(page)
                c_try = _agree(after_nat)
                if (
                    str(after_nat.get("bufKey") or "") == key2
                    and float(after_nat.get("dur") or 0) > 2
                    and c_try["ok"]
                ):
                    break
                page.wait_for_timeout(400)
            c2 = _agree(after_nat)
            c2["key"] = key2
            c2["from"] = key1
            report["checks"]["after_natural_handoff"] = c2
            print(
                f"natural {key1}->{key2} buf={c2['bufKey']} "
                f"cur={c2['uiChord']}/{c2['timelineChord']} "
                f"next={c2['uiNext']}/{c2['timelineNext']} "
                f"match={c2['chordMatch']}/{c2['nextMatch']} ok={c2['ok']}",
                flush=True,
            )
            if not c2["ok"]:
                raise RuntimeError(f"disagree after natural handoff: {c2}")
            if seq and key1 in seq and key2 in seq:
                expect = seq[(seq.index(key1) + 1) % len(seq)]
                if key2 != expect:
                    raise RuntimeError(f"natural skip {key1}->{key2} expect {expect}")

            report["ok"] = True
        except Exception as exc:
            report["error"] = str(exc)
            report["ok"] = False
            try:
                report["fail_probe"] = full_sync_probe(page)
            except Exception:
                pass
        finally:
            try:
                set_cycle_mode(page, False)
                wait_idle(page)
            except Exception:
                pass
            browser.close()
    path = save_report("brief_chord_agree_after_next_8510.json", report)
    print(f"ok={report['ok']} -> {path}")
    if report.get("error"):
        print("ERROR", report["error"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
