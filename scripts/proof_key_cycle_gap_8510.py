"""Focused proof: warm prefetch then measure real pass gap on 8510."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

import walk_creative_backing_matrix as m
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio
from proof_key_cycle_ux_8510 import (
    click_play,
    cycle_ui,
    find_audio,
    open_advanced,
    set_cycle_mode,
    wait_audio,
    wait_sounding,
)

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
DATA = ROOT / "_runtime_key_cycle_8510"
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def read_prefetch() -> list:
    path = DATA / "_kc_prefetch.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def read_gaps() -> list:
    path = DATA / "_key_cycle_pass_gaps.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def main() -> int:
    for name in ("_key_cycle_pass_gaps.jsonl", "_kc_prefetch.jsonl"):
        p = DATA / name
        if p.exists():
            p.unlink()

    report: dict = {"ok": False, "cold_baseline_s": 11.21}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(4000)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Songs")
        page.wait_for_timeout(800)
        page.evaluate(
            """() => {
              const t = [...document.querySelectorAll('button,label,div')].find((el) =>
                /Shape of You/i.test(el.innerText || '')
              );
              if (t) t.click();
            }"""
        )
        page.wait_for_timeout(800)
        goto_studio(page, "Backing")
        page.wait_for_timeout(2500)
        set_cycle_mode(page, True)
        ui = {"sounding": ""}
        for _ in range(20):
            page.wait_for_timeout(500)
            ui = cycle_ui(page)
            if ui.get("sounding") and ui.get("playbar"):
                break
            set_cycle_mode(page, True)
        log(f"cycle on sounding={ui.get('sounding')} hi={ui.get('highlighted')}")

        click_play(page)
        audio = wait_audio(page, 180)
        log(f"audio ready={audio}")

        # Wait until prefetch log shows a completed next-key synth (can be 1–3 min
        # for long catalog forms; fragment runs on the main thread).
        deadline = time.time() + 200
        pref = []
        while time.time() < deadline:
            pref = read_prefetch()
            if any(r.get("ok") and r.get("cached") for r in pref):
                break
            page.wait_for_timeout(2000)
        report["prefetch_before_seek"] = pref
        log(f"prefetch rows={pref}")

        _, h = find_audio(page)
        pre = str(cycle_ui(page).get("sounding") or "")
        gaps_before = len(read_gaps())
        t0 = time.time()
        if h:
            h.evaluate(
                """(a) => {
                  try { a.pause(); } catch (e) {}
                  const d = Number(a.duration) || 0;
                  a.currentTime = Math.max(0, d - 0.25);
                  const p = a.play();
                  if (p && p.catch) p.catch(() => {});
                }"""
            )
        post = wait_sounding(page, pre, 60)
        t1 = time.time()
        gaps = read_gaps()
        pref_after = read_prefetch()
        wall = round(t1 - t0, 2)
        server_gap = gaps[-1]["gap_s"] if gaps and len(gaps) > gaps_before else None
        report.update(
            {
                "before": pre,
                "after": post,
                "wall_s": wall,
                "server_gap_s": server_gap,
                "gaps": gaps,
                "prefetch_after": pref_after,
                "advanced": bool(pre and post and pre != post),
            }
        )
        hits = [r for r in pref_after if r.get("event") == "continue_cache_hit"]
        misses = [r for r in pref_after if r.get("event") == "continue_cache_miss"]
        report["cache_hits"] = hits
        report["cache_misses"] = misses
        improved = server_gap is not None and float(server_gap) < 6.0
        report["ok"] = bool(report["advanced"] and hits)
        log(
            f"advanced={report['advanced']} gap={server_gap} wall={wall} "
            f"hits={len(hits)} misses={len(misses)} ok={report['ok']}"
        )

        set_cycle_mode(page, False)
        page.wait_for_timeout(800)
        browser.close()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "gap_prefetch_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
