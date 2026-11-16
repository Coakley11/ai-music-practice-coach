"""Does an unsaved take survive a refresh - the session ending, rather than the page changing?

Navigation keeps a draft: measured twice, including with a populated snapshot (12/12). But the
trace showed ``_mt_tracks_persist_blob`` EMPTY on every line - the draft only ever lived in the
live session. A browser refresh, a laptop waking from sleep, or a dropped connection starts a NEW
Streamlit session, and anything held only in the old one is gone with it.

This records a take, reloads the page (a new session, exactly as a refresh is), returns to
Multitrack, and checks whether the take can be found anywhere.

Simulated microphone input; a lifecycle measurement, not an instrument test.

Usage:  python -X utf8 scripts/_accept_mt_draft_reload.py http://127.0.0.1:8684
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8684"
SLOT = os.environ.get("MT_SLOT", "Guitar")
#: Long enough to matter. A 3 s take is ~288 KB; a real layer runs the length of the song.
SECONDS = float(os.environ.get("MT_SECONDS", "3"))
#: Press Save layer before the refresh, to measure whether SAVING makes a long take durable.
SAVE_FIRST = os.environ.get("MT_SAVE_BEFORE_REFRESH", "") == "1"
#: Discard before the refresh: the take must NOT come back.
DISCARD_FIRST = os.environ.get("MT_DISCARD_BEFORE_REFRESH", "") == "1"
#: What a Streamlit Cloud restart does to the server's disk: the draft files are gone. The take must
#: NOT come back, and nothing may claim it was saved. Tests the temporary-disk limitation on its own.
WIPE_DRAFTS = os.environ.get("MT_WIPE_DRAFTS_BEFORE_REFRESH", "") == "1"
EXPECT_SURVIVES = not (DISCARD_FIRST or WIPE_DRAFTS)

import _accept_issue78c_visibility as H  # noqa: E402

OUT = SCRIPTS / "evidence-mt-draft"
OUT.mkdir(parents=True, exist_ok=True)
DATA_DIR = Path(os.environ.get("MUSIC_APP_DATA_DIR") or (ROOT / "data"))
GATES: dict[str, bool] = {}


def log(msg: str) -> None:
    print(msg, flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"  {'PASS' if ok else 'FAIL'}  {gate}" + (f"  [{detail}]" if detail else ""))


def rows() -> list[dict]:
    path = DATA_DIR / "_mt_draft_trace.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def slot_fp(row: dict, place: str) -> str | None:
    for p in row.get("slots_with_audio") or []:
        if str(p.get("slot")) == SLOT:
            return (p.get(place) or {}).get("fp")
    return None


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required",
                  "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"])
        context = browser.new_context(viewport={"width": 1400, "height": 950},
                                      permissions=["microphone"])
        page = context.new_page()
        page.set_default_timeout(45000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            H.settle(page, 6)
            mark("R1 the app boots", H.boot(page))
            mark("R2 Multitrack opens", H.goto_multitrack(page))
            H.settle(page, 4)
            mark("R3 a take is recorded", bool(H.record_once(page, SLOT, seconds=SECONDS)),
                 f"{SLOT}, {SECONDS:.0f}s")
            H.settle(page, 8)

            taken = None
            for r in reversed(rows()):
                taken = slot_fp(r, "mt_tracks")
                if taken:
                    break
            size = None
            for r in reversed(rows()):
                for p in r.get("slots_with_audio") or []:
                    if str(p.get("slot")) == SLOT and (p.get("mt_tracks") or {}).get("bytes"):
                        size = (p.get("mt_tracks") or {}).get("bytes")
                        break
                if size:
                    break
            log(f"    take size: {size} bytes ({(size or 0) / 1048576:.2f} MiB; the persist cap is 2.00 MiB)")
            mark("R4 the take is in the live session", bool(taken), f"fp={taken}, {size} bytes")
            blob = None
            for r in reversed(rows()):
                blob = slot_fp(r, "persist_blob")
                if blob:
                    break
            if SAVE_FIRST:
                clicked = H.click_page_button(page, "Save layer", SLOT)
                H.settle(page, 8)
                log(f"    pressed Save layer: {clicked!r}")
                mark("R4b Save layer was pressed", str(clicked).startswith("click"),
                     str(clicked))
                for r in reversed(rows()):
                    blob = slot_fp(r, "persist_blob")
                    if blob:
                        break
                else:
                    blob = None
            log(f"    durable copy (persist blob) before the refresh: {blob or 'NONE'}")
            drafts = list(DATA_DIR.rglob("media/multitrack/drafts/*/*.wav"))
            log(f"    draft files on the server before the refresh: {len(drafts)} "
                f"({sum(p.stat().st_size for p in drafts)} bytes)")
            mark("R4c the take was kept as its own file", len(drafts) >= 1,
                 f"{len(drafts)} draft file(s)")
            if DISCARD_FIRST:
                clicked = H.click_page_button(page, "Discard take", SLOT)
                H.settle(page, 8)
                log(f"    pressed Discard take: {clicked!r}")
                mark("R4d Discard take was pressed", str(clicked).startswith("click"), str(clicked))
                left = list(DATA_DIR.rglob("media/multitrack/drafts/*/*.wav"))
                tombs = list(DATA_DIR.rglob("media/multitrack/drafts/*/*.tombstone"))
                mark("R4e discarding removed the file and left a tombstone",
                     not left and bool(tombs), f"{len(left)} file(s), {len(tombs)} tombstone(s)")
            if WIPE_DRAFTS:
                import shutil
                for d in DATA_DIR.rglob("media/multitrack/drafts"):
                    shutil.rmtree(d, ignore_errors=True)
                log("    wiped the server's draft directory, as a Cloud restart would")
            before = len(rows())

            # A refresh: the browser keeps nothing, the server starts a new session.
            page.reload(wait_until="domcontentloaded")
            H.settle(page, 8)
            H.boot(page)
            H.goto_multitrack(page)
            H.settle(page, 8)

            after = rows()[before:]
            log(f"\n    {len(after)} trace line(s) after the refresh")
            found = None
            where_found = ""
            for r in reversed(after):
                for place in ("mt_tracks", "persist_blob", "page_snapshot", "resolved"):
                    v = slot_fp(r, place)
                    if v:
                        found, where_found = v, place
                        break
                if found:
                    break
            what = "SAVED LAYER" if SAVE_FIRST else "UNSAVED TAKE"
            if EXPECT_SURVIVES:
                mark(f"R5 THE {what} SURVIVED A REFRESH", found == taken and bool(taken),
                     f"found={found} in {where_found or 'nowhere'} (recorded {taken})")
            else:
                why = "DISCARDED" if DISCARD_FIRST else "LOST WITH THE SERVER'S DISK"
                mark(f"R5 A TAKE {why} DID NOT COME BACK", found is None,
                     f"found={found} in {where_found or 'nowhere'}")
            audio = int(page.evaluate("() => document.querySelectorAll('audio').length") or 0)
            log(f"    audio elements on the page after the refresh: {audio}")
            # The status line lives inside the layer's panel, and a closed panel's text is not in
            # innerText - so an earlier version of this failed on a panel nobody had opened.
            try:
                if not H.layer_is_open(page, SLOT):
                    H.toggle_layer_by_pointer(page, SLOT, True)
                    H.settle(page, 3)
            except Exception:
                pass
            text = H.low(H.main_body(page))
            if EXPECT_SURVIVES and found:
                want = "saved layer" if SAVE_FIRST else "unsaved draft"
                mark("R6 the page says what it is", want in text,
                     f"looked for {want!r}")
                if SECONDS > 12:
                    mark("R7 a long take states the temporary-storage limit",
                         "restart of the app can lose" in text)
            if not EXPECT_SURVIVES:
                mark("R6 nothing claims a lost take was saved",
                     "saved layer" not in text or audio == 0, f"{audio} audio element(s)")

            (OUT / "reload.json").write_text(
                json.dumps({"gates": GATES, "taken": taken, "durable_before": blob,
                            "found_after": found, "where": where_found,
                            "trace_after": after}, indent=2), encoding="utf-8")
        finally:
            context.close()
            browser.close()
    passed = sum(1 for ok in GATES.values() if ok)
    log("\n" + "=" * 70)
    for g, ok in GATES.items():
        log(f"  {'PASS' if ok else 'FAIL'}  {g}")
    log(f"\n{passed}/{len(GATES)} gates passed")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
