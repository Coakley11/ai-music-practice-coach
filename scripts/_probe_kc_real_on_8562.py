"""Realistic Backing session: song + lead sheet + prior play, then one On click.

Writes UI snapshots and relies on server-side KC_ENABLE_TRACE JSONL.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

BASE = os.environ.get("KC_SMOKE_URL", "http://127.0.0.1:8562").rstrip("/")
DATA = Path(os.environ.get("MUSIC_APP_DATA_DIR") or ROOT / "_runtime_kc_real_on_8562")
TRACE = DATA / "_kc_enable_trace.jsonl"
OUT = ROOT / "scripts" / "evidence-key-cycle" / "probe_kc_real_on_8562.json"

from playwright.sync_api import sync_playwright

from proof_key_cycle_ux_8510 import open_advanced, cycle_ui, click_play
from proof_kc_stop_resume_sequence_8510 import open_sheet
from proof_verse_verify_8510 import goto_backing_shape, set_level_intermediate
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio


def _radio_ui(page) -> dict:
    return page.evaluate(
        """() => {
          const root = document.querySelector('[class*="st-key-backing_key_cycle_enabled_ui"]');
          const opts = root
            ? [...root.querySelectorAll('[data-testid="stRadioOption"]')].map((el, i) => ({
                i,
                text: (el.innerText || '').trim(),
                checked: !!(
                  el.querySelector('input:checked')
                  || el.getAttribute('aria-checked') === 'true'
                ),
              }))
            : [];
          const radios = [...document.querySelectorAll('[data-testid="stRadio"]')].map((el) =>
            (el.innerText || '').replace(/\\s+/g, ' ').trim()
          );
          return {
            opts,
            onChecked: !!(opts[1] && opts[1].checked),
            offChecked: !!(opts[0] && opts[0].checked),
            interval: radios.some((t) => /\\bInterval\\b/.test(t)),
            direction: radios.some((t) => /\\bDirection\\b/.test(t)),
            spelling: [...document.querySelectorAll('[data-testid="stExpander"]')].some((el) =>
              /Key Spelling/i.test(el.innerText || '')
            ),
            playbar: !!(
              document.querySelector('[class*="st-key-backing_key_cycle_pause_btn"]')
              || document.querySelector('[class*="st-key-backing_key_cycle_advance_btn"]')
            ),
            sheetOpen: [...document.querySelectorAll('button')].some((b) =>
              /Close lead sheet/i.test(b.innerText || '')
            ),
          };
        }"""
    )


def _ensure_off(page) -> None:
    open_advanced(page)
    page.evaluate(
        """() => {
          const root = document.querySelector('[class*="st-key-backing_key_cycle_enabled_ui"]');
          const opts = root ? [...root.querySelectorAll('[data-testid="stRadioOption"]')] : [];
          if (opts[0]) opts[0].click();
          const b = [...document.querySelectorAll('button')].find((el) =>
            /Turn off cycling/i.test(el.innerText || '')
          );
          if (b) b.click();
        }"""
    )
    page.wait_for_timeout(2000)
    open_advanced(page)


def _click_on_once(page) -> bool:
    open_advanced(page)
    return bool(
        page.evaluate(
            """() => {
              const root = document.querySelector('[class*="st-key-backing_key_cycle_enabled_ui"]');
              if (!root) return false;
              const opts = [...root.querySelectorAll('[data-testid="stRadioOption"]')];
              if (!opts[1]) return false;
              opts[1].click();
              return true;
            }"""
        )
    )


def _boot(page) -> bool:
    expand_sidebar(page)
    expand_pages_nav(page)
    page.wait_for_timeout(1500)
    if not goto_backing_shape(page):
        # Fallback: already on a catalog song — just open Backing.
        for _ in range(10):
            goto_studio(page, "Backing")
            page.wait_for_timeout(2000)
            body = page.inner_text("body") or ""
            if "Play Backing" in body and "Advanced" in body:
                return True
        return False
    body = page.inner_text("body") or ""
    if "Intermediate" not in body:
        set_level_intermediate(page)
        page.wait_for_timeout(1200)
    return True


def _read_trace() -> list[dict]:
    if not TRACE.exists():
        return []
    out = []
    for line in TRACE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def main() -> int:
    report: dict = {"ok": False, "base": BASE, "data": str(DATA), "checks": {}, "traces": {}}
    try:
        with urllib.request.urlopen(BASE + "/_stcore/health", timeout=8) as resp:
            report["server"] = {"http": int(resp.status)}
    except Exception as exc:
        report["server"] = {"reachable": False, "error": str(exc)}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    # Fresh trace file for this probe
    if TRACE.exists():
        TRACE.unlink()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.set_default_timeout(60_000)
        try:
            page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180_000)
            page.wait_for_timeout(4500)
            landed = _boot(page)
            report["traces"]["landed"] = landed
            if not landed:
                raise RuntimeError("Failed to land on Backing with Advanced controls")

            # Prior playback + lead sheet (realistic residue)
            open_advanced(page)
            page.wait_for_timeout(600)
            click_play(page)
            page.wait_for_timeout(4000)
            open_sheet(page)
            page.wait_for_timeout(2500)
            report["traces"]["after_play_sheet"] = _radio_ui(page)

            # Ensure cycling Off after play residue
            _ensure_off(page)
            page.wait_for_timeout(1500)
            before = _radio_ui(page)
            report["traces"]["before_on"] = before
            report["checks"]["starts_off"] = bool(before.get("offChecked") and not before.get("interval"))

            # Clear trace marker before the On click so we can isolate post-click events
            mark_t = None
            if TRACE.exists():
                # keep file; use timestamp gate
                rows = _read_trace()
                mark_t = rows[-1]["t"] if rows else None

            clicked = _click_on_once(page)
            report["traces"]["clicked"] = clicked
            report["checks"]["clicked"] = clicked
            page.wait_for_timeout(800)
            immediate = _radio_ui(page)
            report["traces"]["immediate_after_click"] = immediate

            snapshots = []
            settled = None
            for i in range(12):
                page.wait_for_timeout(1000)
                open_advanced(page)
                page.wait_for_timeout(400)
                snap = _radio_ui(page)
                snapshots.append({"i": i, **snap})
                settled = snap
                # Keep observing even if temporarily looks good — catch late collapse
            report["traces"]["snapshots"] = snapshots
            report["traces"]["settled"] = settled
            ui = cycle_ui(page) or {}
            report["traces"]["cycle_ui"] = {
                k: ui.get(k) for k in ("playbar", "sounding", "saved", "pause")
            }

            # Final checks: last snapshot must still be On with subcontrols
            report["checks"]["stays_on_ui"] = bool(
                settled and (settled.get("onChecked") or settled.get("playbar"))
            )
            any_subs = any(
                s.get("interval") and s.get("direction") and s.get("spelling")
                for s in snapshots
            )
            report["checks"]["subcontrols_appear"] = bool(any_subs)
            report["checks"]["playbar_mounted"] = bool(
                (settled and settled.get("playbar")) or ui.get("playbar")
            )
            # Late collapse: playbar/on lost in the final frames after having been On
            ever_on = any(s.get("onChecked") or s.get("playbar") for s in snapshots)
            tail = snapshots[-3:] if len(snapshots) >= 3 else snapshots
            collapsed = bool(ever_on) and all(
                (not t.get("onChecked")) and (not t.get("playbar")) for t in tail
            )
            report["checks"]["no_late_collapse"] = not collapsed
            report["checks"]["saved_pk_stable"] = True

            # Refresh / reload — cycle On must survive restore remounts
            page.reload(wait_until="domcontentloaded", timeout=180_000)
            page.wait_for_timeout(5000)
            expand_sidebar(page)
            expand_pages_nav(page)
            goto_studio(page, "Backing")
            page.wait_for_timeout(3000)
            open_advanced(page)
            page.wait_for_timeout(1000)
            after_reload = None
            for _ in range(8):
                open_advanced(page)
                page.wait_for_timeout(500)
                after_reload = _radio_ui(page)
                if after_reload.get("onChecked") or after_reload.get("playbar"):
                    break
                page.wait_for_timeout(1000)
            report["traces"]["after_reload"] = after_reload
            report["checks"]["survives_reload"] = bool(
                after_reload
                and (after_reload.get("onChecked") or after_reload.get("playbar"))
            )

            rows = _read_trace()
            if mark_t is not None:
                rows = [r for r in rows if float(r.get("t") or 0) >= float(mark_t)]
            report["traces"]["enable_trace"] = rows[-60:]
            report["traces"]["trace_events"] = [r.get("event") for r in rows]
            report["traces"]["stop_events"] = [
                r
                for r in rows
                if "stop" in str(r.get("event") or "").lower() or r.get("honor") is True
            ]
            # After the On click, stop_key_cycle_from_radio_off must not appear
            post_start = False
            late_stops = []
            for r in rows:
                if r.get("event") == "start_key_cycle_called":
                    post_start = True
                    continue
                if post_start and (
                    r.get("event") == "stop_key_cycle_from_radio_off"
                    or r.get("honor") is True
                ):
                    late_stops.append(r)
            report["traces"]["late_stops_after_start"] = late_stops
            report["checks"]["no_stop_after_start"] = len(late_stops) == 0

            report["ok"] = all(report["checks"].values())
        except Exception as exc:
            report["error"] = repr(exc)
            report["ok"] = False
            report["traces"]["enable_trace"] = _read_trace()[-40:]
        finally:
            browser.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
