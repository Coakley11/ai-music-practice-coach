"""The populated-snapshot case: does an older snapshot take a newer unsaved take with it?

The single-slot run showed the draft surviving - and the trace showed why: no page snapshot for
that slot existed, and ``apply_page_snapshot`` skips a snapshot only when it is ENTIRELY empty of
multitrack content. So the draft was protected by accident.

This builds the case that is not accidental:

  1. record into the first slot,
  2. navigate away and back, so a snapshot is written that HOLDS that layer,
  3. record a second, unsaved take into another slot,
  4. navigate away,
  5. come back - and see whether both are still there.

Every verdict reads the app's own trace (sizes and fingerprints only) and the page's own content.
Navigation is proved by the trace saying which page each run was on, because a helper returning
True proved nothing: an earlier version of this reported 8/8 while no navigation had happened.

A simulated microphone is not a saxophone. This measures the take lifecycle, not how an
instrument sounds.

Usage:  python -X utf8 scripts/_accept_mt_draft_two_slots.py http://127.0.0.1:8682
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

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8682"
FIRST = os.environ.get("MT_FIRST_SLOT", "Guitar")
SECOND = os.environ.get("MT_SECOND_SLOT", "Sax / winds")

import _accept_issue78c_visibility as H  # noqa: E402

OUT = SCRIPTS / "evidence-mt-draft"
OUT.mkdir(parents=True, exist_ok=True)
DATA_DIR = Path(os.environ.get("MUSIC_APP_DATA_DIR") or (ROOT / "data"))
GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"  {'PASS' if ok else 'FAIL'}  {gate}" + (f"  [{detail}]" if detail else ""))


def note(msg: str) -> None:
    NOTES.append(msg)
    log(f"  OBS   {msg}")


def rows() -> list[dict]:
    path = DATA_DIR / "_mt_draft_trace.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def where(slot: str, row: dict) -> dict:
    for p in row.get("slots_with_audio") or []:
        if str(p.get("slot")) == slot:
            return p
    return {}


def fp(slot: str, row: dict, place: str) -> str | None:
    return ((where(slot, row).get(place) or {}) or {}).get("fp")


def show(label: str, since: int) -> int:
    new = rows()[since:]
    log(f"\n  --- trace: {label} ({len(new)} line(s)) ---")
    for r in new:
        bits = []
        for slot in (FIRST, SECOND):
            p = where(slot, r)
            if p:
                bits.append("%s[live=%s snap=%s resolved=%s]" % (
                    slot, (p.get("mt_tracks") or {}).get("fp", "-"),
                    (p.get("page_snapshot") or {}).get("fp", "-"),
                    (p.get("resolved") or {}).get("fp", "-")))
        log(f"    {str(r.get('stage'))[:40]:<40} page={str(r.get('studio_page'))[:11]:<12} "
            + ("  ".join(bits) or "(nothing)"))
    return len(rows())


def audio_count(page: Page) -> int:
    try:
        return int(page.evaluate("() => document.querySelectorAll('audio').length") or 0)
    except Exception:
        return 0


def leave_and_return(page: Page, label: str, seen: int) -> tuple[int, bool]:
    H.click_practice_page(page)
    H.settle(page, 8)
    seen = show(f"away ({label})", seen)
    on_other = any(str(r.get("studio_page")) != "multitrack" for r in rows()[-6:])
    H.goto_multitrack(page)
    H.settle(page, 8)
    seen = show(f"back ({label})", seen)
    return seen, on_other


def main() -> int:
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
            mark("T1 the app boots", H.boot(page))
            mark("T2 Multitrack opens", H.goto_multitrack(page))
            H.settle(page, 4)
            seen = len(rows())

            # 1. the first layer
            mark("T3 a take is recorded into the first slot",
                 bool(H.record_once(page, FIRST, seconds=3.0)), FIRST)
            H.settle(page, 8)
            seen = show("after recording the first slot", seen)
            first_fp = None
            for r in reversed(rows()):
                first_fp = fp(FIRST, r, "mt_tracks")
                if first_fp:
                    break
            mark("T4 the first slot holds audio", bool(first_fp), f"fp={first_fp}")

            # 2. a round trip, so a snapshot that HOLDS that layer exists
            seen, left_once = leave_and_return(page, "to populate the snapshot", seen)
            mark("T5 the first round trip really left Multitrack", left_once)
            snap_fp = None
            for r in reversed(rows()):
                snap_fp = fp(FIRST, r, "page_snapshot")
                if snap_fp:
                    break
            mark("T6 the snapshot now HOLDS the first layer - the case that is not accidental",
                 bool(snap_fp), f"snapshot fp={snap_fp}")
            if not snap_fp:
                note("no snapshot ever captured the first layer, so this run cannot test the "
                     "populated-snapshot case - the guard would skip an empty snapshot anyway")

            # 3. the second, unsaved take. Its panel has to be open before the recorder in it
            # can be driven - the first attempt at this failed for that reason alone.
            try:
                if not H.layer_is_open(page, SECOND):
                    H.toggle_layer_by_pointer(page, SECOND, True)
                    H.settle(page, 4)
            except Exception as exc:
                note(f"could not open the {SECOND} panel: {exc}")
            second_ok = bool(H.record_once(page, SECOND, seconds=3.0))
            if not second_ok:
                for alt in ("Bass", "Piano / Keys", "Extra layer"):
                    try:
                        if not H.layer_is_open(page, alt):
                            H.toggle_layer_by_pointer(page, alt, True)
                            H.settle(page, 3)
                        if H.record_once(page, alt, seconds=3.0):
                            note(f"recorded into {alt} instead of {SECOND}")
                            globals()["SECOND"] = alt
                            second_ok = True
                            break
                    except Exception:
                        continue
            mark("T7 a second take is recorded into another slot", second_ok, SECOND)
            H.settle(page, 8)
            seen = show("after recording the second slot", seen)
            second_fp = None
            for r in reversed(rows()):
                second_fp = fp(SECOND, r, "mt_tracks")
                if second_fp:
                    break
            mark("T8 the second slot holds audio before navigating", bool(second_fp),
                 f"fp={second_fp}")
            before_count = audio_count(page)

            # 4 & 5. away and back
            seen, left_twice = leave_and_return(page, "the real test", seen)
            mark("T9 the second round trip really left Multitrack", left_twice)

            last = rows()[-1] if rows() else {}
            live_first = fp(FIRST, last, "mt_tracks")
            live_second = fp(SECOND, last, "mt_tracks")
            res_second = fp(SECOND, last, "resolved")
            after_count = audio_count(page)

            mark("T10 the saved first layer is still there", bool(live_first),
                 f"fp={live_first} (was {first_fp})")
            mark("T11 THE UNSAVED SECOND TAKE SURVIVED", bool(live_second),
                 f"live={live_second} (was {second_fp}) resolved={res_second}")
            mark("T12 both takes are offered on the page", after_count >= before_count,
                 f"{before_count} audio element(s) before, {after_count} after")

            if second_fp and not live_second:
                note("REPRODUCED: the newer unsaved take is gone from mt_tracks after a round "
                     f"trip while the older layer ({live_first}) survived"
                     + (f"; its bytes are still reachable as {res_second}" if res_second
                        else "; and its bytes are not reachable anywhere"))

            (OUT / "two-slot.json").write_text(
                json.dumps({"gates": GATES, "notes": NOTES, "first_fp": first_fp,
                            "second_fp": second_fp, "live_first": live_first,
                            "live_second": live_second, "trace": rows()}, indent=2),
                encoding="utf-8")
        finally:
            context.close()
            browser.close()

    passed = sum(1 for ok in GATES.values() if ok)
    log("\n" + "=" * 70)
    for g, ok in GATES.items():
        log(f"  {'PASS' if ok else 'FAIL'}  {g}")
    for n in NOTES:
        log(f"  OBS   {n}")
    log(f"\n{passed}/{len(GATES)} gates passed")
    log("NOTE: simulated microphone input, not a real instrument.")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
