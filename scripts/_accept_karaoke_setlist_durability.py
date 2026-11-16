"""Does a saved Karaoke setlist stay saved? A real app, a real browser, isolated data.

The app is pointed at scripts/_fake_supabase.py (a local stand-in for the Supabase REST API) through
environment variables only, under an isolated test user and the dev app's strict-egress policy. No
real Supabase project is read or written. The harness owns both processes, so it can do what a
Streamlit Cloud restart or redeploy does: replace the app server - and its local disk - while "the
cloud" stays.

Every gate reads three places: what the stand-in cloud holds, what the server disk holds, and what
the page shows. A setlist that is only on the server's disk is NOT saved: a restart loses it.

    python -X utf8 scripts/_accept_karaoke_setlist_durability.py [scenario ...]

Scenarios: build (always), stale_tab, end_set, restart, clear_confirm, save_failure, empty_guard.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from _accept_issue69_karaoke_transposition import click_key, click_text, settle, wait_for_app  # noqa: E402
from _accept_karaoke_qa import ROWS_JS, open_karaoke  # noqa: E402
from walk_creative_backing_matrix import click_nav, expand_sidebar, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

CLOUD_PORT = int(os.environ.get("KS_CLOUD_PORT", "8761"))
APP_PORT = int(os.environ.get("KS_APP_PORT", "8762"))
URL = f"http://127.0.0.1:{APP_PORT}"
EVID = SCRIPTS / "evidence-karaoke-setlist"
EVID.mkdir(parents=True, exist_ok=True)
CLOUD_DB = EVID / "cloud.json"
CLOUD_LOG = EVID / "cloud-requests.jsonl"
CLOUD_FAIL_FLAG = EVID / "cloud-fail-writes.flag"
TEST_USER = "ksetlist_isolated_test"
SONGS = [("Shape of You", "Pop"), ("Perfect", "Pop"), ("Let It Be", "Rock")]
WANT = [s for s, _ in SONGS]

RESULTS: list[tuple[str, bool, str]] = []
NOTES: list[str] = []
PROCS: dict[str, subprocess.Popen] = {}


def mark(gate: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((gate, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {gate}" + (f"  [{detail}]" if detail else ""), flush=True)
    return bool(ok)


def note(msg: str) -> None:
    NOTES.append(msg)
    print(f"    {msg}", flush=True)


# ---------------------------------------------------------------- processes

def _kill_tree(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    try:
        proc.wait(timeout=10)
    except Exception:
        pass


def _listening(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def start_cloud(fresh: bool) -> None:
    if fresh:
        for p in (CLOUD_DB, CLOUD_LOG, CLOUD_FAIL_FLAG):
            p.unlink(missing_ok=True)
    if _listening(CLOUD_PORT):
        raise SystemExit(f"REFUSING: something already serves {CLOUD_PORT}")
    PROCS["cloud"] = subprocess.Popen(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "_fake_supabase.py"), str(CLOUD_PORT), str(CLOUD_DB), str(CLOUD_LOG), str(CLOUD_FAIL_FLAG)],
        stdout=subprocess.DEVNULL, stderr=open(EVID / "cloud-server.log", "a"),
    )
    for _ in range(30):
        if _listening(CLOUD_PORT):
            return
        time.sleep(0.5)
    raise SystemExit("stand-in cloud did not start")


def start_app(data_dir: Path, tag: str) -> None:
    if _listening(APP_PORT):
        raise SystemExit(f"REFUSING: something already serves {APP_PORT}")
    env = dict(os.environ)
    env.update({
        "SUITE_SUPABASE_URL": f"http://127.0.0.1:{CLOUD_PORT}",
        "SUITE_SUPABASE_KEY": "isolated-test-key-not-a-secret",
        "SUITE_USER_ID": TEST_USER,
        "MUSIC_EGRESS_STRICT": "1",
        "MUSIC_APP_DATA_DIR": str(data_dir),
    })
    log = open(EVID / f"app-{tag}.log", "w")
    PROCS["app"] = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "streamlit_music_practice_app.py",
         "--server.port", str(APP_PORT), "--server.headless", "true", "--server.fileWatcherType", "none"],
        cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    for _ in range(90):
        if PROCS["app"].poll() is not None:
            raise SystemExit(f"app server died; see app-{tag}.log")
        if _listening(APP_PORT):
            return
        time.sleep(1)
    raise SystemExit("app server did not answer")


def stop_app() -> None:
    _kill_tree(PROCS.pop("app", None))
    for _ in range(20):
        if not _listening(APP_PORT):
            return
        time.sleep(0.5)


# ---------------------------------------------------------------- the three places

def _queue_in(obj) -> list | None:
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if "karaoke_queue" in cur and isinstance(cur["karaoke_queue"], list):
                return cur["karaoke_queue"]
            stack.extend(v for v in cur.values() if isinstance(v, (dict, list)))
        elif isinstance(cur, list):
            stack.extend(v for v in cur if isinstance(v, (dict, list)))
    return None


def _brief(queue: list | None) -> list[tuple[str, str]] | None:
    if queue is None:
        return None
    return [(str(e.get("title") or e.get("pick_key") or "?"), str(e.get("practice_key") or "")) for e in queue
            if isinstance(e, dict)]


def cloud_setlist() -> list[tuple[str, str]] | None:
    """The setlist in the stand-in cloud's music row for the test user (None = no setlist key)."""
    if not CLOUD_DB.exists():
        return None
    db = json.loads(CLOUD_DB.read_text(encoding="utf-8") or "{}")
    rows = [r for r in db.get("suite_app_current_state", []) if str(r.get("app") or "").startswith("music")]
    if not rows:
        return None
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    full = ((rows[0].get("metrics") or {}).get("full_session") or {})
    return _brief(((full.get("session") or {}).get("karaoke_queue")) if isinstance(full.get("session"), dict) else _queue_in(full))


DISK_FILES: dict[str, object] = {}


def disk_setlist(data_dir: Path) -> list[tuple[str, str]] | None:
    """The setlist in the server disk's music state. Every such file is recorded in DISK_FILES."""
    DISK_FILES.clear()
    found = None
    for p in sorted(data_dir.rglob("*music*state*.json")):
        try:
            q = _queue_in(json.loads(p.read_text(encoding="utf-8")))
        except Exception as exc:
            DISK_FILES[str(p.relative_to(data_dir))] = f"unreadable {type(exc).__name__}"
            continue
        DISK_FILES[str(p.relative_to(data_dir))] = None if q is None else len(q)
        if found is None and p.name == "music_user_state.json":
            found = _brief(q)
    return found


def ui_setlist(page: Page) -> list[str]:
    click_nav(page, "Songs")
    settle(page, 3)
    open_karaoke(page)
    settle(page, 3)
    try:
        return [str(r.get("label") or "") for r in (page.evaluate(ROWS_JS) or [])]
    except Exception:
        return []


def titles(brief) -> list[str]:
    return [t for t, _ in (brief or [])]


def in_order(labels: list[str], want: list[str]) -> bool:
    if len(labels) != len(want):
        return False
    return all(w.lower() in (lab or "").lower() for lab, w in zip(labels, want))


def shot(page: Page, name: str) -> None:
    try:
        page.screenshot(path=str(EVID / f"{name}.png"), full_page=True)
    except Exception:
        pass


def body(page: Page) -> str:
    try:
        return page.inner_text("body") or ""
    except Exception:
        return ""


# ---------------------------------------------------------------- browser steps

def new_page(browser, width: int = 1500):
    ctx = browser.new_context(viewport={"width": width, "height": 1000})
    page = ctx.new_page()
    page.set_default_timeout(30000)
    page.goto(URL, wait_until="domcontentloaded")
    settle(page, 6)
    wait_for_app(page)
    return ctx, page


def to_voice(page: Page) -> None:
    expand_sidebar(page)
    set_baseweb_select(page, "Instrument", "Voice")
    settle(page, 6)


def add_song(page: Page, title: str, genre: str) -> bool:
    if not pick_song(page, NOTES, title, genre):
        return False
    settle(page, 3)
    click_nav(page, "Songs")
    settle(page, 3)
    ok = click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
    settle(page, 5)
    return bool(ok)


def page_change(page: Page) -> None:
    """Ordinary navigation: each page change is an intentional save the strict policy lets through."""
    click_nav(page, "Songs")
    settle(page, 4)
    click_nav(page, "Practice") or click_nav(page, "Home")
    settle(page, 4)


def three_places(gate: str, page: Page | None, data_dir: Path, want: list[str]) -> None:
    c, d = cloud_setlist(), disk_setlist(data_dir)
    u = ui_setlist(page) if page is not None else None
    note(f"{gate}: cloud={titles(c) if c is not None else None} keys={[k for _, k in (c or [])]} "
         f"disk={titles(d) if d is not None else None} page={u}")
    note(f"    disk files (setlist length per file): {DISK_FILES}")
    mark(f"{gate} - in the cloud, in order", titles(c) == want, f"cloud={titles(c) if c is not None else 'no setlist key'}")
    if page is not None:
        mark(f"{gate} - on the page, in order", in_order(u or [], want), f"{len(u or [])} row(s)")


def status_text(page: Page) -> str:
    try:
        loc = page.locator('[class*="st-key-karaoke_setlist_save_status"]')
        return (loc.first.inner_text(timeout=3000) or "").strip() if loc.count() else ""
    except Exception:
        return ""


def edits_on_new_server(page: Page, data_dir: Path) -> None:
    """Deliberate changes still work - and a failed save says so."""
    click_nav(page, "Songs")
    settle(page, 3)
    open_karaoke(page)
    # Remove the second song deliberately.
    removed = click_key(page, "karaoke_rm_1_")
    settle(page, 5)
    mark("D1 a single song can be removed deliberately", bool(removed))
    three_places("D2 after removing Perfect", page, data_dir, ["Shape of You", "Let It Be"])
    st_txt = status_text(page)
    mark("D3 the page says the setlist was saved to the account", "saved to your account" in st_txt.lower(), st_txt[:90])

    # A cloud outage: the next edit must NOT claim success.
    CLOUD_FAIL_FLAG.write_text("1", encoding="utf-8")
    add_song(page, "Love Story", "Country")
    click_nav(page, "Songs")
    settle(page, 3)
    open_karaoke(page)
    st_txt = status_text(page)
    note(f"status during the outage: {st_txt[:160]!r}")
    mark("F1 a save the cloud refused is reported as NOT saved", "not saved to your account" in st_txt.lower(), st_txt[:90])
    mark("F2 the cloud still holds the last saved setlist", titles(cloud_setlist()) == ["Shape of You", "Let It Be"],
         f"{titles(cloud_setlist())}")
    CLOUD_FAIL_FLAG.unlink(missing_ok=True)
    retried = click_key(page, "karaoke_setlist_save_retry") or click_text(page, "Retry saving setlist")
    settle(page, 6)
    st_txt = status_text(page)
    mark("F3 Retry saves it, and says so", bool(retried) and "saved to your account" in st_txt.lower(), st_txt[:90])
    three_places("F4 after the retry", page, data_dir, ["Shape of You", "Let It Be", "Love Story"])

    # Clear Setlist asks first; Keep leaves everything; Yes erases deliberately and stays erased.
    click_key(page, "karaoke_clear_queue")
    settle(page, 4)
    asked = "erase all 3 songs" in body(page).lower()
    mark("C1 Clear Setlist asks before erasing", asked)
    three_places("C2 while it asks, nothing is erased", page, data_dir, ["Shape of You", "Let It Be", "Love Story"])
    click_key(page, "karaoke_clear_confirm_no")
    settle(page, 4)
    three_places("C3 Keep the setlist keeps it", page, data_dir, ["Shape of You", "Let It Be", "Love Story"])
    click_key(page, "karaoke_clear_queue")
    settle(page, 4)
    click_key(page, "karaoke_clear_confirm_yes")
    settle(page, 6)
    c = cloud_setlist()
    mark("C4 Yes erases it deliberately, in the cloud too", c == [], f"cloud={titles(c) if c is not None else None}")
    page.reload(wait_until="domcontentloaded")
    settle(page, 8)
    mark("C5 and a deliberate clear stays cleared after a refresh", len(ui_setlist(page)) == 0)


# ---------------------------------------------------------------- run

def main() -> int:
    wanted = set(sys.argv[1:]) or {"stale_tab", "end_set", "restart"}
    data1 = Path(tempfile.mkdtemp(prefix="ks-disk1-"))
    data2 = Path(tempfile.mkdtemp(prefix="ks-disk2-"))
    start_cloud(fresh=True)
    start_app(data1, "server1")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            stale_ctx = stale = None
            if "stale_tab" in wanted:
                # Another tab or device, opened BEFORE the setlist exists and left open.
                stale_ctx, stale = new_page(browser)
                to_voice(stale)
                note(f"stale tab opened; it sees {len(ui_setlist(stale))} setlist row(s)")
                click_nav(stale, "Songs")
                settle(stale, 3)

            ctx, page = new_page(browser)
            to_voice(page)
            added = [add_song(page, t, g) for t, g in SONGS]
            mark("B1 three songs were added", all(added), f"{added}")
            saved_msg = body(page)
            note("save message on the page: " + ("'saved' wording present" if "saved" in saved_msg.lower() else "none found"))
            three_places("B2 after building", page, data1, WANT)
            built_keys = [k for _, k in (cloud_setlist() or [])]
            mark("B3 each song kept its own key", len(built_keys) == 3 and all(built_keys), f"{built_keys}")
            shot(page, "b-built")

            page.reload(wait_until="domcontentloaded")
            settle(page, 8)
            three_places("B4 after a refresh", page, data1, WANT)

            if stale is not None:
                stale.bring_to_front()
                page_change(stale)
                page_change(stale)
                three_places("S1 after the stale tab navigates", None, data1, WANT)
                ds = disk_setlist(data1)
                mark("S2 the stale tab did not empty the server disk", titles(ds) == WANT,
                     f"disk={titles(ds) if ds is not None else None}")
                # The next day: a NEW session on the same server, after the stale tab's save and
                # before tab A saves again. It restores from that server disk.
                nctx, npage = new_page(browser)
                three_places("S3 a new session opened after the stale tab's save", npage, data1, WANT)
                shot(npage, "s3-new-session")
                page_change(npage)
                page_change(npage)
                three_places("S4 after that new session navigates", npage, data1, WANT)
                nctx.close()

            if "end_set" in wanted:
                click_nav(page, "Songs")
                settle(page, 3)
                open_karaoke(page)
                shot(page, "e-before-start")
                started = click_key(page, "karaoke_start_session") or click_text(page, "Start Karaoke Set")
                if not started:
                    try:
                        page.get_by_role("button", name=re.compile("Start Karaoke Set")).first.click(timeout=8000)
                        started = True
                    except Exception as exc:
                        note(f"start button: {type(exc).__name__}: {str(exc)[:160]}")
                settle(page, 8)
                shot(page, "e-performing")
                performing = "end karaoke set" in body(page).lower()
                note(f"performing page offers End karaoke set: {performing}")
                ended = click_key(page, "karaoke_inline_end_set")
                if not ended:
                    click_nav(page, "Songs")
                    settle(page, 3)
                    open_karaoke(page)
                    ended = click_key(page, "karaoke_stop_session") or click_text(page, "End Karaoke Set")
                settle(page, 6)
                mark("E1 a set was started and ended", bool(started and ended), f"start={started} end={ended}")
                three_places("E2 after End Set", page, data1, WANT)
                page.reload(wait_until="domcontentloaded")
                settle(page, 8)
                three_places("E3 after End Set and a refresh", page, data1, WANT)

            ctx.close()
            if stale_ctx is not None:
                stale_ctx.close()

            if "restart" in wanted:
                # What a Cloud restart or redeploy does: a new server with an empty disk.
                stop_app()
                start_app(data2, "server2")
                ctx2, page2 = new_page(browser)
                three_places("R1 after the server was replaced (new session, empty disk)", page2, data2, WANT)
                shot(page2, "r-after-restart")
                page_change(page2)
                three_places("R2 and it stays after the new session navigates", page2, data2, WANT)
                if "edits" in wanted:
                    edits_on_new_server(page2, data2)
                ctx2.close()
            browser.close()
    finally:
        stop_app()
        _kill_tree(PROCS.pop("cloud", None))
        shutil.rmtree(data1, ignore_errors=True)
        shutil.rmtree(data2, ignore_errors=True)
        (EVID / "results.json").write_text(json.dumps({"results": RESULTS, "notes": NOTES}, indent=1), encoding="utf-8")
    failed = [g for g, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} gates passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
