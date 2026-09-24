"""Focused: Verse → Verse+Chorus auto-apply without Play (8510)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from proof_kc_bpm_feel_scope_8510 import (  # noqa: E402
    commit_sections,
    open_advanced_visible,
    read_server,
    wait_controls_ready,
)
from proof_kc_finish_five_8510 import audio_probe, clear_pause_hold, wait_idle  # noqa: E402
from proof_kc_focused_shared_8510 import (  # noqa: E402
    boot_cycle_verse,
    play_until_audible,
    save_report,
    sounding,
    timeline_info,
    wait_src_change,
)
from proof_kc_manual_review_gaps_8510 import set_multi_scope, wav_duration_from_url  # noqa: E402
from proof_kc_settings_focused_8510 import set_scope_selected_section  # noqa: E402
from proof_kc_stop_resume_sequence_8510 import open_sheet  # noqa: E402
from proof_key_cycle_ux_8510 import click_pause_ordinary, set_cycle_mode  # noqa: E402


def _live_chart_sections(page) -> dict:
    return page.evaluate(
        """() => {
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const doc = f.contentDocument;
              if (!doc || !doc.querySelector('.live-follow-shell')) continue;
              const text = doc.body ? (doc.body.innerText||'') : '';
              return {
                hasVerse: /Verse/i.test(text),
                hasChorus: /Chorus/i.test(text),
              };
            } catch (e) {}
          }
          return {hasVerse:false, hasChorus:false};
        }"""
    )


def _force_verse_only(page, src_hint: str) -> dict:
    """Commit Verse-only via proven tag-remove path; wait for audible replace."""
    open_advanced_visible(page)
    wait_controls_ready(page)
    set_scope_selected_section(page, "Verse")
    wait_idle(page, 20000)
    scope = commit_sections(page, ["Verse 1"])
    wait_idle(page, 45000)
    src0 = str(audio_probe(page).get("src") or src_hint)
    # Auto-apply should replace V+C audio with Verse-only.
    after = wait_src_change(page, src0, 150)
    page.wait_for_timeout(2000)
    open_sheet(page)
    wait_idle(page)
    # Poll until timeline/duration reflect Verse-only (tags alone are not enough).
    t0 = time.time()
    tl = {}
    src = str(after.get("src") or audio_probe(page).get("src") or src0)
    dur = wav_duration_from_url(src) or float(after.get("dur") or audio_probe(page).get("dur") or 0)
    while time.time() - t0 < 120:
        open_sheet(page)
        tl = timeline_info(page)
        secs = tl.get("sections") or []
        src = str(audio_probe(page).get("src") or src)
        dur = wav_duration_from_url(src) or float(audio_probe(page).get("dur") or dur or 0)
        no_chorus = bool(secs) and not any("Chorus" in s for s in secs)
        shorter = bool(dur > 1 and dur < 90)  # V+C Shape ~121s; Verse-only much shorter
        if no_chorus or shorter:
            break
        page.wait_for_timeout(2000)
    srv = read_server(page)
    return {
        "src": src,
        "dur": dur,
        "timeline": tl,
        "tags": srv.get("tags") or scope.get("after"),
        "key": sounding(page),
        "scope_commit": scope,
        "src_changed_from_hint": bool(src and src != src_hint),
    }


def _add_chorus_to_scope(page) -> dict:
    """Add Chorus 1 to the selected-sections multiselect (ordinary UI)."""
    open_advanced_visible(page)
    wait_controls_ready(page)
    set_scope_selected_section(page, "Verse")
    wait_idle(page, 15000)
    before = list(read_server(page).get("tags") or [])
    # Prefer Streamlit multiselect key; fall back to generic.
    root = page.locator(
        '[class*="st-key-backing_track_multi_sections"] input, '
        '[data-testid="stMultiSelect"] input'
    ).first
    added = False
    try:
        root.click(timeout=5000)
        page.wait_for_timeout(500)
        page.get_by_role("option", name="Chorus 1", exact=True).click(timeout=5000)
        added = True
    except Exception as exc1:
        # Fallback: typeahead
        try:
            root.click(timeout=3000)
            page.keyboard.type("Chorus 1", delay=40)
            page.wait_for_timeout(400)
            page.keyboard.press("Enter")
            added = True
            exc1 = None
        except Exception as exc2:
            return {"ok": False, "before": before, "error": f"{exc1} | {exc2}"}
    wait_idle(page, 20000)
    t0 = time.time()
    tags = list(read_server(page).get("tags") or [])
    while time.time() - t0 < 40:
        tags = list(read_server(page).get("tags") or [])
        has_v = any("Verse" in t for t in tags)
        has_c = any("Chorus" in t for t in tags)
        if has_v and has_c:
            return {"ok": True, "before": before, "after": tags, "added": added}
        page.wait_for_timeout(1000)
    # Last-chance set_multi_scope
    ok = set_multi_scope(page, ["Verse 1", "Chorus 1"])
    tags = list(read_server(page).get("tags") or [])
    return {
        "ok": bool(ok and any("Chorus" in t for t in tags)),
        "before": before,
        "after": tags,
        "added": added,
        "fallback_multi": ok,
    }


def main() -> int:
    report: dict = {"proof": "verse_to_vc_auto", "checks": {}, "ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 2200})
        try:
            boot_cycle_verse(page)
            base = play_until_audible(page)
            clear_pause_hold(page)
            open_sheet(page)
            wait_idle(page)

            verse = _force_verse_only(page, str(base.get("src") or ""))
            report["before"] = verse
            tags0 = [str(t) for t in (verse.get("tags") or [])]
            tl0 = verse.get("timeline") or {}
            secs0 = tl0.get("sections") or []
            has_chorus0 = any("Chorus" in s for s in secs0) or any(
                "Chorus" in t for t in tags0
            )
            if has_chorus0:
                raise RuntimeError(
                    f"setup still has Chorus after Verse-only: tags={tags0} sections={secs0}"
                )
            if not any("Verse" in t for t in tags0) and not any(
                "Verse" in s for s in secs0
            ):
                raise RuntimeError(f"setup missing Verse after Verse-only: tags={tags0}")
            dur0 = float(verse.get("dur") or 0)
            if dur0 > 90:
                raise RuntimeError(f"Verse-only duration still long: {dur0}")

            # Pause so the Verse pass cannot advance mid V+C regenerate.
            click_pause_ordinary(page)
            wait_idle(page, 10000)
            clear_pause_hold(page)

            src0 = str(verse.get("src") or "")
            key0 = sounding(page) or verse.get("key")

            wait_controls_ready(page)
            scope_add = _add_chorus_to_scope(page)
            report["scope_commit"] = scope_add
            if not scope_add.get("ok"):
                raise RuntimeError(f"add Chorus failed: {scope_add}")
            wait_idle(page, 60000)
            after = wait_src_change(page, src0, 150)
            src1 = str(after.get("src") or "")
            page.wait_for_timeout(2500)
            open_sheet(page)
            wait_idle(page)
            # Poll until timeline includes Chorus
            t0 = time.time()
            tl1 = timeline_info(page)
            dur1 = 0.0
            while time.time() - t0 < 120:
                tl1 = timeline_info(page)
                secs1 = tl1.get("sections") or []
                src1 = str(audio_probe(page).get("src") or src1)
                dur1 = wav_duration_from_url(src1) or float(
                    audio_probe(page).get("dur") or 0
                )
                if any("Chorus" in s for s in secs1) and any(
                    "Verse" in s for s in secs1
                ):
                    break
                if dur0 > 1 and dur1 > dur0 * 1.5:
                    break
                page.wait_for_timeout(2000)
            key1 = sounding(page)
            secs1 = tl1.get("sections") or []
            has_v = any("Verse" in s for s in secs1)
            has_c = any("Chorus" in s for s in secs1)
            longer = bool(
                (dur0 > 1 and dur1 > dur0 * 1.12)
                or (
                    tl0.get("end", 0) > 0
                    and tl1.get("end", 0) > float(tl0.get("end") or 0) * 1.12
                )
                or (
                    tl0.get("len", 0) > 0
                    and tl1.get("len", 0) > int(tl0.get("len") or 0) * 1.2
                )
            )
            srv = read_server(page)
            tags = [str(t) for t in (srv.get("tags") or [])]
            live = _live_chart_sections(page)
            sections_ok = bool(
                (has_v and has_c)
                or (
                    any("Verse" in t for t in tags)
                    and any("Chorus" in t for t in tags)
                    and live.get("hasVerse")
                    and live.get("hasChorus")
                )
            )
            report["after"] = {
                "key": key1,
                "src": src1,
                "dur": dur1,
                "timeline": tl1,
                "tags": tags,
                "live": live,
                "src_changed": bool(src1 and src1 != src0),
                "key_preserved": key0 == key1,
            }
            report["checks"]["audible_vc"] = {
                "ok": bool(
                    src1
                    and src1 != src0
                    and key0 == key1
                    and sections_ok
                    and (longer or (live.get("hasChorus") and dur1 > 1))
                ),
                "has_verse": has_v or bool(live.get("hasVerse")),
                "has_chorus": has_c or bool(live.get("hasChorus")),
                "duration_or_timeline_grew": longer,
                "sections_ok": sections_ok,
                **report["after"],
            }
            report["checks"]["chart_sections"] = {
                "ok": bool(live.get("hasVerse") and live.get("hasChorus")),
                "live": live,
            }
            report["ok"] = all(c.get("ok") for c in report["checks"].values())
            if not report["ok"]:
                raise RuntimeError(
                    f"Verse+Chorus replace incomplete: {report['checks']['audible_vc']}"
                )
        except Exception as exc:
            report["error"] = str(exc)
            report["ok"] = False
            try:
                page.screenshot(
                    path=str(ROOT / "scripts/evidence-key-cycle/verse_vc_fail.png"),
                    full_page=True,
                )
            except Exception:
                pass
        finally:
            try:
                set_cycle_mode(page, False)
                wait_idle(page)
            except Exception:
                pass
            browser.close()
    path = save_report("verse_to_vc_auto_8510.json", report)
    print(f"ok={report['ok']} -> {path}")
    if report.get("error"):
        print("ERROR", report["error"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
