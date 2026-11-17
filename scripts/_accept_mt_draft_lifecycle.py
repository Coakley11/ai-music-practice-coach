"""Record a take, go somewhere else, come back: is the unsaved draft still there?

The reported loss, in the musician's words: recorded a Guitar layer on a laptop, never pressed
Save Layer, visited another page, came back, and the recording was gone.

This drives that exact sequence in a real browser with Chromium's fake capture device, and reads
the app's own draft trace (MUSIC_MT_DRAFT_TRACE=1) to see where the audio was at each transition -
``mt_tracks``, ``_mt_tracks_persist_blob``, the page snapshot, and what
``resolve_multitrack_slot_bytes`` answers. Sizes and fingerprints only; no audio content is read.

A simulated microphone is NOT a saxophone. This measures the take's lifecycle - that a recording
exists, survives navigation, plays, saves and discards - and says nothing about how an instrument
sounds through a real microphone.

Usage:  python -X utf8 scripts/_accept_mt_draft_lifecycle.py http://127.0.0.1:8680
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8680"
SLOT = os.environ.get("MT_SLOT", "Guitar")

import _accept_issue78c_visibility as H  # noqa: E402

OUT = SCRIPTS / "evidence-mt-draft"
OUT.mkdir(parents=True, exist_ok=True)
GATES: dict[str, bool] = {}
NOTES: list[str] = []
DATA_DIR = Path(os.environ.get("MUSIC_APP_DATA_DIR") or (ROOT / "data"))


def log(msg: str) -> None:
    print(msg, flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"  {'PASS' if ok else 'FAIL'}  {gate}" + (f"  [{detail}]" if detail else ""))


def note(msg: str) -> None:
    NOTES.append(msg)
    log(f"  OBS   {msg}")


def trace_rows() -> list[dict]:
    path = DATA_DIR / "_mt_draft_trace.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def show_trace(label: str, since: int = 0) -> list[dict]:
    rows = trace_rows()[since:]
    log(f"\n  --- app draft trace: {label} ({len(rows)} new line(s)) ---")
    for r in rows:
        places = r.get("slots_with_audio") or []
        summary = ", ".join(
            "%s[live=%s blob=%s snap=%s resolved=%s]" % (
                p.get("slot"),
                (p.get("mt_tracks") or {}).get("fp", "-"),
                (p.get("persist_blob") or {}).get("fp", "-"),
                (p.get("page_snapshot") or {}).get("fp", "-"),
                (p.get("resolved") or {}).get("fp", "-"),
            ) for p in places) or "(no slot holds audio anywhere)"
        log(f"    {r.get('stage'):<42} page={r.get('studio_page','')!r:<14} {summary}")
    return trace_rows()


def layer_shows_audio(page: Page, slot: str) -> dict:
    """What the Multitrack page itself says about this slot."""
    return page.evaluate(
        """(slot) => {
            const s = slot.toLowerCase();
            const out = {panel: false, audio_elements: 0, text: ''};
            for (const d of document.querySelectorAll('details')) {
              const t = (d.innerText || '').toLowerCase();
              if (!t.includes(s)) continue;
              out.panel = true;
              out.audio_elements = d.querySelectorAll('audio').length;
              out.text = (d.innerText || '').slice(0, 300);
              break;
            }
            if (!out.panel) {
              const body = document.querySelector('[data-testid=stMain]') || document.body;
              out.text = (body.innerText || '').slice(0, 300);
              out.audio_elements = document.querySelectorAll('audio').length;
            }
            return out;
        }""",
        slot,
    )


def main() -> int:
    seen = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required",
                  "--use-fake-device-for-media-stream",
                  "--use-fake-ui-for-media-stream"],
        )
        context = browser.new_context(viewport={"width": 1400, "height": 950},
                                      permissions=["microphone"])
        page = context.new_page()
        page.set_default_timeout(45000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            H.settle(page, 6)
            mark("D1 the app boots", H.boot(page))
            mark("D2 the Multitrack page opens", H.goto_multitrack(page))
            H.settle(page, 4)
            seen = len(trace_rows())

            # ---- record a take into the slot ------------------------------------------
            recorded = H.record_once(page, SLOT, seconds=3.0)
            H.settle(page, 8)
            mark("D3 a take was recorded into the layer", bool(recorded),
                 f"slot={SLOT}")
            after_record = layer_shows_audio(page, SLOT)
            log(f"    the page shows: audio elements={after_record.get('audio_elements')}")
            seen = len(show_trace("after recording", seen))

            rows = trace_rows()
            landed = [r for r in rows if (r.get("slots_with_audio_count") or 0) > 0]
            mark("D4 the app holds audio for a slot after recording", bool(landed),
                 f"{len(landed)} trace line(s) with audio")

            # ---- go somewhere else, exactly as the musician did -----------------------
            # PROVED by the page's own content, not by a helper's return value: the first run of
            # this measured 8/8 "the draft survived" while the trace showed page='multitrack'
            # throughout and no page-change save at all - the navigation had never happened.
            left = H.click_practice_page(page)
            H.settle(page, 8)
            away_text = H.low(H.main_body(page))
            really_left = ("multitrack" not in away_text) or ("practice" in away_text and
                                                              "record — " not in away_text)
            log(f"    page after leaving mentions multitrack: {'multitrack' in away_text}")
            mark("D5 navigated away, proved by the page's own content",
                 bool(left) and really_left,
                 f"helper={bool(left)} left_multitrack={really_left}")
            seen = len(show_trace("after navigating away", seen))

            # ---- and come back --------------------------------------------------------
            back = H.goto_multitrack(page)
            H.settle(page, 8)
            mark("D6 navigated back to Multitrack", bool(back))
            seen = len(show_trace("after returning to Multitrack", seen))

            after_return = layer_shows_audio(page, SLOT)
            rows = trace_rows()
            on_return = [r for r in rows
                         if str(r.get("stage") or "").startswith("multitrack_page:")]
            last = on_return[-1] if on_return else {}
            places = last.get("slots_with_audio") or []
            mine = [p for p in places if str(p.get("slot")) == SLOT]
            live_fp = (mine[0].get("mt_tracks") or {}).get("fp") if mine else None
            resolved_fp = (mine[0].get("resolved") or {}).get("fp") if mine else None
            snap_fp = (mine[0].get("page_snapshot") or {}).get("fp") if mine else None

            mark("D7 THE DRAFT SURVIVED: the slot still holds its audio on return",
                 bool(live_fp),
                 f"live={live_fp} snapshot={snap_fp} resolved={resolved_fp}")
            mark("D8 the returned page offers the take to review",
                 int(after_return.get("audio_elements") or 0) > 0,
                 f"{after_return.get('audio_elements')} audio element(s) on the page")
            if not live_fp and resolved_fp:
                note("the bytes are still reachable through resolve_multitrack_slot_bytes "
                     f"({resolved_fp}) but mt_tracks no longer holds them - the draft was "
                     "overwritten in the live session, not lost from the device")

            (OUT / "draft-lifecycle.json").write_text(
                json.dumps({"gates": GATES, "notes": NOTES, "trace": trace_rows(),
                            "page_after_record": after_record,
                            "page_after_return": after_return}, indent=2),
                encoding="utf-8")
        finally:
            context.close()
            browser.close()

    passed = sum(1 for ok in GATES.values() if ok)
    log("\n" + "=" * 70)
    for gate, ok in GATES.items():
        log(f"  {'PASS' if ok else 'FAIL'}  {gate}")
    for n in NOTES:
        log(f"  OBS   {n}")
    log(f"\n{passed}/{len(GATES)} gates passed")
    log("NOTE: a simulated microphone is not a saxophone - this is a lifecycle measurement.")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
