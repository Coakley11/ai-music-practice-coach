"""Reliable Shape→Backing boot + Verse1/loops=1 vs buffer-duration diagnosis on 8510."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from playwright.sync_api import sync_playwright

from proof_kc_finish_five_8510 import clear_pause_hold, wait_idle
from proof_kc_focused_shared_8510 import play_until_audible
from proof_kc_written_shape_display_8510 import audio_snap
from proof_key_cycle_ux_8510 import click_play, set_cycle_mode
from proof_verse_verify_8510 import configure_verse, read_canon, set_level_intermediate
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_guitar_shape_key import ensure_songs_catalog_source, pick_active_song_from_dropdown

OUT = ROOT / "scripts" / "evidence-key-cycle" / "diag_short_arrangement_8510.json"
BASE = "http://127.0.0.1:8510"


def force_expand_sidebar(page) -> None:
    page.evaluate(
        """() => {
          const btns = [...document.querySelectorAll('button, [role="button"]')];
          for (const b of btns) {
            const al = ((b.getAttribute('aria-label') || '') + (b.innerText || '')).toLowerCase();
            if (/expand|keyboard_double_arrow_right|chevron_right/.test(al)) {
              b.click();
              return;
            }
          }
        }"""
    )
    page.wait_for_timeout(600)
    expand_sidebar(page)
    expand_pages_nav(page)


def click_studio_page(page, name: str) -> bool:
    """Click a studio page without falling through to disabled Open.nth indexes."""
    force_expand_sidebar(page)
    return bool(
        page.evaluate(
            """(name) => {
              const needle = String(name || '').toLowerCase();
              const side = document.querySelector('section[data-testid="stSidebar"]');
              const roots = side ? [side, document] : [document];
              for (const root of roots) {
                const buttons = [...root.querySelectorAll('button')];
                const hit = buttons.find((b) => {
                  const t = (b.innerText || '').trim().toLowerCase();
                  return t === needle || t.endsWith(needle) || t.includes(needle);
                });
                if (hit && !hit.disabled) {
                  hit.scrollIntoView({block: 'center'});
                  hit.click();
                  return true;
                }
              }
              return false;
            }""",
            name,
        )
    )


def wait_backing_ready(page, seconds: float = 60.0) -> dict:
    deadline = time.time() + seconds
    last = {}
    while time.time() < deadline:
        last = page.evaluate(
            """() => {
              const body = document.body.innerText || '';
              return {
                play: /Play Backing Track/i.test(body),
                scope: /Playback scope/i.test(body),
                shape: /Shape of You/i.test(body),
                loops: /Loop count|Number of repeats/i.test(body),
                keyCycle: /Key Cycle|Cycle keys/i.test(body),
              };
            }"""
        )
        if last.get("play") or last.get("scope"):
            return {**last, "ok": True}
        page.wait_for_timeout(800)
    return {**last, "ok": False}


def boot_shape_backing(page) -> dict:
    page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
    page.wait_for_timeout(3000)
    clear_pause_hold(page)
    force_expand_sidebar(page)
    notes: list[str] = []
    # Prefer Songs page, but Active Song dropdown can exist without a nav hit.
    click_studio_page(page, "Songs")
    wait_idle(page, 4000)
    ensure_songs_catalog_source(page, notes)
    drop_ok = pick_active_song_from_dropdown(page, "Shape of You")
    wait_idle(page, 5000)
    set_level_intermediate(page)
    wait_idle(page, 3000)
    body = page.inner_text("body") or ""
    shape_ok = "Shape of You" in body
    backing_clicked = False
    ready = {"ok": False}
    for _ in range(8):
        backing_clicked = click_studio_page(page, "Backing") or click_studio_page(
            page, "Backing Track"
        )
        wait_idle(page, 5000)
        set_level_intermediate(page)
        ready = wait_backing_ready(page, 25)
        if ready.get("ok") and ready.get("shape"):
            break
    return {
        "notes": notes,
        "drop_ok": drop_ok,
        "shape_ok": shape_ok,
        "backing_clicked": backing_clicked,
        "ready": ready,
        "ok": bool(ready.get("ok") and (ready.get("shape") or shape_ok)),
    }


def ui_probe(page) -> dict:
    return page.evaluate(
        """() => {
          const body = document.body.innerText || '';
          const canonLine = (body.match(/backing canonical:[^\\n]+/i) || [''])[0];
          const loopRoot = document.querySelector('[class*="st-key-backing_track_loops"]');
          const loopSlider = loopRoot && loopRoot.querySelector('input[type="range"]');
          const scopeRoot = document.querySelector('[class*="st-key-backing_track_scope"]');
          let scopeChecked = '';
          if (scopeRoot) {
            const checked = scopeRoot.querySelector('input[type="radio"]:checked');
            const lab = checked && (checked.closest('label') || checked.closest('[data-testid="stRadioOption"]'));
            scopeChecked = lab ? (lab.innerText || '').trim() : '';
          }
          const tags = [...document.querySelectorAll('[data-baseweb="tag"]')]
            .map((el) => (el.innerText || '').trim())
            .filter(Boolean)
            .slice(0, 12);
          return {
            canonLine: canonLine.slice(0, 280),
            loopSlider: loopSlider ? Number(loopSlider.value) : null,
            scopeChecked,
            sectionTags: tags,
            hasPlayBacking: /Play Backing Track/i.test(body),
            hasShape: /Shape of You/i.test(body),
          };
        }"""
    )


def identity_probe(page) -> dict:
    return page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const a = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          const cmd = window.__kcLastCmd || {};
          const liveSection = ((document.body.innerText || '').match(/Now Playing:\\s*([^\\n]+)/i) || ['',''])[1].trim();
          return {
            dualEnabled: !!dual.enabled,
            bufUrl: a ? (a.getAttribute('data-kc-url') || a.src || '').slice(-80) : '',
            bufDur: a ? Number(a.duration || 0) : 0,
            bufSounding: a ? (a.getAttribute('data-kc-sounding') || '') : '',
            cmdSounding: cmd.sounding || '',
            cmdUrl: (cmd.currentUrl || '').slice(-80),
            cmdPassToken: cmd.passToken || '',
            liveSection,
          };
        }"""
    )


def classify(dur: float, canon: dict, ui: dict, cfg: dict) -> str:
    sec = str((canon or {}).get("sec") or "").strip()
    scope = str((canon or {}).get("scope") or "").strip()
    loops = 0
    try:
        loops = int((canon or {}).get("loops") or 0)
    except Exception:
        loops = 0
    if loops <= 0:
        try:
            loops = int((ui or {}).get("loopSlider") or 0)
        except Exception:
            loops = 0
    tags = list((ui or {}).get("sectionTags") or [])
    verse_ui = any("Verse" in t for t in tags) or ("Verse" in sec)
    selected = scope == "Selected sections" or "Selected" in str(
        (ui or {}).get("scopeChecked") or ""
    )
    committed_short = bool(
        selected and verse_ui and loops == 1 and bool((cfg or {}).get("loops_ok"))
    )
    if 5 < dur < 120:
        return "short_ok"
    if dur >= 200:
        return "stale_full_song_audio" if committed_short else "full_song_uncommitted_or_unknown"
    if dur <= 0:
        return "no_audio"
    return "unexpected_duration"


def main() -> int:
    report: dict = {"ok": False, "short_env": "unset"}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        try:
            boot = boot_shape_backing(page)
            report["boot"] = boot
            print("boot", json.dumps(boot)[:600], flush=True)
            if not boot.get("ok"):
                report["error"] = "backing_boot_failed"
                raise RuntimeError("backing_boot_failed")

            report["after_boot"] = {"ui": ui_probe(page), "canon": read_canon(page)}
            cfg = configure_verse(page, loops=1)
            wait_idle(page, 4000)
            report["after_configure"] = {
                "cfg": cfg,
                "ui": ui_probe(page),
                "canon": read_canon(page),
            }
            print(
                "after_configure",
                json.dumps(report["after_configure"], indent=2)[:1400],
                flush=True,
            )

            set_cycle_mode(page, True)
            wait_idle(page, 8000)
            clear_pause_hold(page)
            click_play(page)
            # Fail fast: full-song Intermediate Shape is ~421s; Verse×1 is ~40s.
            # Do not wait minutes for a stale buffer to "become" short.
            deadline = time.time() + 75
            snap = audio_snap(page)
            aud = {"note": "pending"}
            while time.time() < deadline:
                snap = audio_snap(page)
                dur_now = float(snap.get("dur") or 0)
                if dur_now >= 200:
                    break
                if dur_now > 1 and not snap.get("paused"):
                    aud = play_until_audible(page, 20) if aud.get("note") == "pending" else aud
                    if dur_now > 1:
                        break
                page.wait_for_timeout(700)
            if aud.get("note") == "pending":
                try:
                    aud = play_until_audible(page, 25)
                except Exception as exc:
                    aud = {"error": str(exc)}
            page.wait_for_timeout(1500)
            snap = audio_snap(page)
            ident = identity_probe(page)
            ui = ui_probe(page)
            canon = read_canon(page)
            dur = float(snap.get("dur") or ident.get("bufDur") or 0)
            report["playing"] = {
                "audible": aud,
                "snap": snap,
                "identity": ident,
                "ui": ui,
                "canon": canon,
                "dur": dur,
            }
            report["classification"] = classify(dur, canon, ui, cfg)
            report["ok"] = report["classification"] == "short_ok"
            print(
                f"RESULT dur={dur} class={report['classification']} "
                f"scope={canon.get('scope')} sec={canon.get('sec')} "
                f"loops={canon.get('loops')} tags={ui.get('sectionTags')}",
                flush=True,
            )
        except Exception as exc:
            report["error"] = str(exc)
            print("ERROR", exc, flush=True)
        finally:
            try:
                set_cycle_mode(page, False)
            except Exception:
                pass
            browser.close()

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}", flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
