"""Does an ~86 s Multitrack layer, saved with Save layer AND Save project, survive a Cloud restart?

A real app in a real browser, pointed at scripts/_fake_supabase.py (a local stand-in for the Supabase
REST + Storage APIs) through environment variables only, under an isolated test user and the dev
app's strict-egress policy. No real Supabase project is touched. The harness owns both processes, so
it can replace the app server and its disk - what a Streamlit Cloud restart or redeploy does - while
"the cloud" (tables + bucket) stays.

It distinguishes four things, because they are different:
  * Save layer      - marks the take saved in the session/workspace save (capped at 2 MiB)
  * Save project    - writes the project to the library: tracks as their own media files
  * server disk     - temporary: replaced by a restart
  * the cloud       - the stand-in's tables and bucket: what survives a restart

    python -X utf8 scripts/_accept_mt_save_project_durability.py
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
EVID = SCRIPTS / "evidence-mt-save-project"
EVID.mkdir(parents=True, exist_ok=True)
DATA1 = Path(tempfile.mkdtemp(prefix="mtsp-disk1-"))
DATA2 = Path(tempfile.mkdtemp(prefix="mtsp-disk2-"))
os.environ["MUSIC_APP_DATA_DIR"] = str(DATA1)  # before the helpers read it
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from playwright.sync_api import Page, sync_playwright  # noqa: E402

import _accept_issue78c_visibility as H  # noqa: E402

SECONDS = float(os.environ.get("MT_SECONDS", "86"))
SLOT = "Guitar"
CLOUD_PORT, APP_PORT = 8781, 8782
URL = f"http://127.0.0.1:{APP_PORT}"
H.URL = URL  # its boot() navigates to its own URL global
CLOUD_DB = EVID / "cloud.json"
STORE = EVID / "cloud-storage"
FAKE_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.isolated-test-not-a-secret"
TEST_USER = "mt_isolated_test"
PROJECT = "Durability 86s"

RESULTS: list[tuple[str, bool, str]] = []
TAKE_SECONDS = [0.0]
PROCS: dict[str, subprocess.Popen] = {}


def mark(gate: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((gate, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {gate}" + (f"  [{detail}]" if detail else ""), flush=True)
    return bool(ok)


def note(msg: str) -> None:
    print(f"    {msg}", flush=True)


def listening(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def kill(proc) -> None:
    if proc is not None and proc.poll() is None:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)


def start_cloud() -> None:
    for p in (CLOUD_DB, EVID / "cloud-requests.jsonl"):
        p.unlink(missing_ok=True)
    shutil.rmtree(STORE, ignore_errors=True)
    if listening(CLOUD_PORT):
        raise SystemExit(f"REFUSING: {CLOUD_PORT} is in use")
    PROCS["cloud"] = subprocess.Popen(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "_fake_supabase.py"), str(CLOUD_PORT), str(CLOUD_DB),
         str(EVID / "cloud-requests.jsonl")], stdout=subprocess.DEVNULL, stderr=open(EVID / "cloud-server.log", "a"))
    for _ in range(30):
        if listening(CLOUD_PORT):
            return
        time.sleep(0.5)
    raise SystemExit("stand-in cloud did not start")


def start_app(data: Path, tag: str) -> None:
    if listening(APP_PORT):
        raise SystemExit(f"REFUSING: {APP_PORT} is in use")
    env = dict(os.environ)
    env.update({"SUITE_SUPABASE_URL": f"http://127.0.0.1:{CLOUD_PORT}", "SUITE_SUPABASE_KEY": FAKE_KEY,
                "SUITE_USER_ID": TEST_USER, "MUSIC_EGRESS_STRICT": "1", "MUSIC_APP_DATA_DIR": str(data),
                "MUSIC_MT_DRAFT_TRACE": "1"})
    PROCS["app"] = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "streamlit_music_practice_app.py", "--server.port", str(APP_PORT),
         "--server.headless", "true", "--server.fileWatcherType", "none"],
        cwd=str(ROOT), env=env, stdout=open(EVID / f"app-{tag}.log", "w"), stderr=subprocess.STDOUT)
    for _ in range(90):
        if PROCS["app"].poll() is not None:
            raise SystemExit(f"app died; see app-{tag}.log")
        if listening(APP_PORT):
            return
        time.sleep(1)
    raise SystemExit("app did not answer")


def stop_app() -> None:
    kill(PROCS.pop("app", None))
    for _ in range(20):
        if not listening(APP_PORT):
            return
        time.sleep(0.5)


def trace_rows(data: Path) -> list[dict]:
    p = data / "_mt_draft_trace.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def live_fp(data: Path, after: int = 0) -> tuple[str | None, int | None]:
    for r in reversed(trace_rows(data)[after:]):
        for s in r.get("slots_with_audio") or []:
            if str(s.get("slot")) == SLOT:
                m = s.get("mt_tracks") or {}
                if m.get("fp"):
                    return m["fp"], m.get("bytes")
    return None, None


def wav_info(data: bytes) -> dict:
    try:
        with wave.open(io.BytesIO(data)) as w:
            return {"decodes": True, "seconds": round(w.getnframes() / float(w.getframerate()), 2),
                    "rate": w.getframerate(), "channels": w.getnchannels()}
    except Exception as exc:
        return {"decodes": False, "error": type(exc).__name__}


def cloud_objects() -> list[tuple[str, bytes]]:
    if not STORE.exists():
        return []
    return [(str(p.relative_to(STORE)), p.read_bytes()) for p in sorted(STORE.rglob("*")) if p.is_file()]


def cloud_tables() -> dict:
    return json.loads(CLOUD_DB.read_text(encoding="utf-8") or "{}") if CLOUD_DB.exists() else {}


def fill(page: Page, key: str, text: str) -> bool:
    loc = page.locator(f'[class*="st-key-{key}"] input, [class*="st-key-{key}"] textarea')
    if not loc.count():
        return False
    loc.first.scroll_into_view_if_needed()
    loc.first.fill(text)
    loc.first.press("Enter")
    return True


def click_key(page: Page, prefix: str) -> bool:
    loc = page.locator(f'[class*="st-key-{prefix}"] button')
    for i in range(loc.count()):
        b = loc.nth(i)
        try:
            if b.is_visible() and b.is_enabled():
                b.scroll_into_view_if_needed()
                b.click()
                return True
        except Exception:
            continue
    return False


def open_expanders(page: Page, words: tuple[str, ...]) -> None:
    for s in page.locator("summary").all():
        try:
            t = (s.inner_text() or "").lower()
            if any(w in t for w in words):
                det = s.locator("xpath=..")
                if det.get_attribute("open") is None:
                    s.click()
                    H.settle(page, 1.5)
        except Exception:
            continue


def new_context(browser):
    ctx = browser.new_context(viewport={"width": 1400, "height": 950}, permissions=["microphone"])
    page = ctx.new_page()
    page.set_default_timeout(45000)
    page.goto(URL, wait_until="domcontentloaded")
    H.settle(page, 6)
    H.boot(page)
    return ctx, page


def reopen_and_check(browser, data: Path, want_fp: str, label: str) -> dict:
    ctx, page = new_context(browser)
    before = len(trace_rows(data))
    try:
        H.goto_multitrack(page)
        H.settle(page, 6)
        open_expanders(page, ("project", "library", "saved"))
        H.settle(page, 2)
        txt = H.low(H.main_body(page))
        listed = PROJECT.lower() in txt
        mark(f"{label}: the saved project is listed", listed)
        loaded = click_key(page, "mt_hist_load_")
        H.settle(page, 10)
        note(f"{label}: a Load button was offered: {loaded}")
        fp, size = live_fp(data, before)
        mark(f"{label}: the layer is back WITHOUT pressing anything", fp == want_fp, f"fp={fp} want={want_fp} bytes={size}")
        if fp != want_fp:
            # What a user could do: New Project clears only the working session (the saved library
            # row is untouched), then Load the saved project from the library.
            txt2 = H.low(H.main_body(page))
            note(f"{label}: shown as currently loaded: {'loaded project' in txt2}; "
                 f"'record or upload at least one layer' shown: {'record or upload at least one layer' in txt2}")
            before2 = len(trace_rows(data))
            cleared = click_key(page, "mt_new_project_btn")
            H.settle(page, 8)
            open_expanders(page, ("project", "library", "saved", "all projects"))
            H.settle(page, 2)
            loaded2 = click_key(page, "mt_hist_load_")
            H.settle(page, 15)
            fp, size = live_fp(data, before2)
            mark(f"{label}: after New Project + Load, the layer comes back with the SAME audio", fp == want_fp,
                 f"new={cleared} load={loaded2} fp={fp} want={want_fp} bytes={size}")
        H.shot(page, f"reopen-{label.split()[0].lower()}")
        return {"fp": fp, "bytes": size}
    finally:
        ctx.close()


def main() -> int:
    start_cloud()
    start_app(DATA1, "server1")
    take_sha = None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=[
                "--autoplay-policy=no-user-gesture-required", "--use-fake-device-for-media-stream",
                "--use-fake-ui-for-media-stream"])
            ctx, page = new_context(browser)
            mark("P1 Multitrack opens", H.goto_multitrack(page))
            H.settle(page, 4)
            mark("P2 a full-length take is recorded", bool(H.record_once(page, SLOT, seconds=SECONDS)), f"{SECONDS:.0f}s")
            H.settle(page, 10)
            fp, size = live_fp(DATA1)
            mark("P3 the take is in the live session", bool(fp), f"fp={fp} {size} bytes ({(size or 0) / 1048576:.2f} MiB)")
            drafts = list(DATA1.rglob("media/multitrack/drafts/*/*.wav"))
            if drafts:
                raw = drafts[0].read_bytes()
                take_sha = hashlib.sha256(raw).hexdigest()
                info = wav_info(raw)
                TAKE_SECONDS[0] = float(info.get("seconds") or 0)
                note(f"the recorder stopped at {TAKE_SECONDS[0]:.2f} s of the {SECONDS:.0f} s asked for")
                mark("P4 the recorded take decodes", bool(info.get("decodes")) and TAKE_SECONDS[0] > 60, f"{info}")
            clicked = H.click_page_button(page, "Save layer", SLOT)
            H.settle(page, 8)
            mark("P5 Save layer pressed", str(clicked).startswith("click"), str(clicked))

            # Save project to the library.
            open_expanders(page, ("project", "library", "save"))
            H.settle(page, 2)
            filled = fill(page, "mt_history_save_name", PROJECT)
            H.settle(page, 2)
            saved = click_key(page, "mt_history_save_new_btn") or click_key(page, "mt_history_save_as_new_btn") \
                or click_key(page, "mt_history_save_changes_btn")
            H.settle(page, 15)
            mark("P6 Save project pressed", filled and saved, f"name={filled} save={saved}")
            body = H.low(H.main_body(page))
            note("project save message: " + next((ln for ln in body.splitlines() if "project" in ln and "sav" in ln), "(none found)")[:160])
            H.shot(page, "after-save-project")
            ctx.close()

            # What reached "the cloud": bucket objects and the library row.
            objs = cloud_objects()
            note("objects in the stand-in bucket: " + json.dumps([(k, len(v)) for k, v in objs]))
            match = [(k, v) for k, v in objs if take_sha and hashlib.sha256(v).hexdigest() == take_sha]
            mark("C1 the take's exact bytes are in cloud storage", bool(match),
                 f"{match[0][0] if match else 'no object with the take SHA-256'}")
            if match:
                mark("C2 the cloud copy decodes, same length as recorded", wav_info(match[0][1]).get("seconds") == TAKE_SECONDS[0],
                     f"{wav_info(match[0][1])}")
            tabs = cloud_tables()
            saved_items = tabs.get("suite_saved_items", [])
            catalog_hit = any(PROJECT in json.dumps(r) for r in saved_items)
            mark("C3 the project is in the cloud library", catalog_hit, f"{len(saved_items)} saved item(s)")
            state_rows = [r for r in tabs.get("suite_app_current_state", []) if str(r.get("app", "")).startswith("music")]
            ws_has_audio = any(take_sha and take_sha[:8] in json.dumps(r) for r in state_rows)
            note(f"workspace row carries the take inline: {ws_has_audio} (the 2 MiB cap drops it - expected False)")

            # Same server, a genuinely new session (another tab or device on the same account).
            if take_sha:
                reopen_and_check(browser, DATA1, take_sha[:8], "N1 new session, same server")

            # A Streamlit Cloud restart or redeploy: new server, empty disk, the cloud stays.
            stop_app()
            start_app(DATA2, "server2")
            got = reopen_and_check(browser, DATA2, (take_sha or "")[:8], "R1 after the server was replaced") if take_sha else {}
            restored = [p for p in DATA2.rglob("*.wav") if take_sha and hashlib.sha256(p.read_bytes()).hexdigest() == take_sha]
            note(f"restored copies on the new server's disk with the take's SHA-256: {len(restored)}")
            if restored:
                mark("R2 the restored audio decodes, same length as recorded", wav_info(restored[0].read_bytes()).get("seconds") == TAKE_SECONDS[0],
                     f"{wav_info(restored[0].read_bytes())}")
                # Synchronized playback: the restored layer and the project's stored backing through
                # the real transport component, timed like slice 78A.
                try:
                    import _accept_issue78a_transport as T
                    from multitrack_align_contract import transport_payload

                    backing = max((v for k, v in objs if hashlib.sha256(v).hexdigest() != take_sha), key=len, default=None)
                    layer = restored[0].read_bytes()
                    tracks = [{"id": "t0", "name": SLOT, "b64": "data:audio/wav;base64," + T.b64(layer), "volume": 1.0,
                               "mute": False, "solo": False, "delay": 0.0, **transport_payload(0.0)}]
                    T.WORK.mkdir(parents=True, exist_ok=True)
                    sctx = browser.new_context(viewport={"width": 1200, "height": 800})
                    res = T.run_case(sctx, "restored-project-playback", tracks=tracks, backing=backing, bpm=96,
                                     count_in_bars=0)
                    sctx.close()
                    spread = float(res.get("actual_start_spread_sec") or 0.0)
                    mark("S1 restored layer + project backing start together",
                         res.get("sources", 0) >= (2 if backing else 1) and spread <= 0.005 and not res.get("js_errors"),
                         f"sources={res.get('sources')} spread={spread * 1000:.2f} ms backing={'project' if backing else 'none stored'} errors={res.get('js_errors')}")
                except Exception as exc:
                    mark("S1 restored layer + project backing start together", False, f"{type(exc).__name__}: {exc}")
            if take_sha:
                reopen_and_check(browser, DATA2, take_sha[:8], "N2 another new session after the restart")
            browser.close()
    finally:
        stop_app()
        kill(PROCS.pop("cloud", None))
        (EVID / "results.json").write_text(json.dumps(RESULTS, indent=1), encoding="utf-8")
        shutil.rmtree(DATA1, ignore_errors=True)
        shutil.rmtree(DATA2, ignore_errors=True)
    failed = [g for g, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} gates passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
