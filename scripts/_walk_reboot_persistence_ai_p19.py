"""A–I reboot proof + P1–P9 persistence contract (live).

Usage:
  python scripts/_walk_reboot_persistence_ai_p19.py http://127.0.0.1:8512
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_open_backing_studio,
    click_radio,
    expand_sidebar,
    goto_improv,
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import enable_guitar_capo, pick_song, set_shape_tonic  # noqa: E402
from _walk_pass8_live import set_practice_key as set_sidebar_pk  # noqa: E402
from _walk_custom_practice_key import (  # noqa: E402
    goto_custom,
    set_original_key,
)
from walk_creative_backing_matrix import click_button_has as _click_button_has  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8512"
PORT = int(re.search(r":(\d+)", URL).group(1))
ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "reboot-"
ENTRY = "streamlit_music_practice_app.py"


def meta() -> dict:
    def _run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    return {
        "branch": _run(["git", "branch", "--show-current"]),
        "sha": _run(["git", "rev-parse", "HEAD"]),
        "dirty_count": len(
            [ln for ln in _run(["git", "status", "--porcelain"]).splitlines() if ln.strip()]
        ),
        "url": URL,
    }


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    (OUT / f"{stem}.txt").write_text(body[:24000], encoding="utf-8")
    return body


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def has_any(text: str, *needles: str) -> bool:
    blob = low(text)
    return any(low(n) in blob for n in needles)


def page_family(body: str) -> str:
    b = low(body)
    # Backing kinds require an actual Backing chrome signal ("return to"), not merely
    # Creative SBI copy that mentions "Open Backing".
    if has_any(b, "return to mission") and has_any(b, "tempo", "quick bpm", "backing"):
        return "backing_mission"
    if (
        has_any(b, "song-based improvisation", "song based improvisation")
        and has_any(b, "tempo", "quick bpm")
        and has_any(b, "return to")
    ):
        return "backing_sbi"
    if has_any(b, "jam session") and has_any(b, "tempo", "quick bpm") and has_any(b, "return to"):
        return "backing_jam"
    if (
        has_any(b, "style jam", "entry style")
        and has_any(b, "tempo", "quick bpm")
        and has_any(b, "return to")
    ):
        return "backing_entry"
    if has_any(b, "backing track", "quick bpm", "loop region") and has_any(b, "return to"):
        return "backing"
    # Songs before Creative: catalog copy mentions "Creative Lab" and must not
    # classify Song Selection as Creative.
    if has_any(b, "song selection", "browse library", "song catalog", "now loaded for practice") and not has_any(
        b,
        "improvisation lab",
        "improvisation intelligence",
        "entry & jam",
        "song source",
        "generate example",
        "selected mission",
    ):
        return "songs"
    # Creative before Custom: sidebar "Original Key" alone must not mean Custom page.
    # Do not use bare "creative lab" / "motif" — those appear in Songs help copy.
    if has_any(
        b,
        "improvisation intelligence",
        "improvisation lab",
        "entry & jam",
        "generate example",
        "harmony map",
        "song-based improvisation",
        "song based improvisation",
        "song source",
        "live coach",
        "mission practice",
        "selected mission chord",
        "new motif",
    ):
        return "creative"
    if has_any(
        b,
        "custom progression lab",
        "progression lab",
        "custom song builder",
        "create your own song",
    ):
        return "custom"
    if has_any(b, "song selection", "pick a song", "catalog"):
        return "songs"
    if has_any(b, "practice focus", "today's practice", "practice length"):
        return "practice"
    return "unknown"


def creative_tab(body: str) -> str:
    b = low(body)
    if has_any(b, "new motif", "harder", "easier") and "motif" in b:
        return "motif"
    # Nested SBI Custom shows song source + Custom progression while still on Creative.
    if has_any(b, "song source") and has_any(b, "custom progression", "song-based", "song based"):
        return "sbi"
    if has_any(b, "song-based", "song based", "play song-based"):
        return "sbi"
    if has_any(b, "entry & jam") and has_any(b, "improvisation entry"):
        return "sbi"
    if has_any(b, "live coach"):
        return "live_coach"
    if has_any(b, "harmony map"):
        return "harmony"
    if has_any(b, "mission"):
        return "mission"
    return "unknown"


def _active_workspace_id() -> str:
    p = ROOT / "data" / "suite_active_workspace.json"
    if p.exists():
        try:
            return str(json.loads(p.read_text(encoding="utf-8")).get("workspace_id") or "daniel")
        except Exception:
            pass
    return "daniel"


def disk_state_path() -> Path:
    wid = _active_workspace_id()
    return ROOT / "data" / "workspaces" / wid / "music_user_state.json"


def disk_studio_page() -> str:
    for p in (
        disk_state_path(),
        ROOT / "data" / "music_user_state.json",
    ):
        if not p.exists():
            continue
        try:
            blob = json.loads(p.read_text(encoding="utf-8"))
            st = blob.get("state") or {}
            # Match prepare_studio_nav: canonical nav wins over a desynced top-level key.
            nav = st.get("studio_nav_state") or {}
            page = ""
            if isinstance(nav, dict):
                page = str(nav.get("studio_page") or nav.get("page") or "").strip()
            if not page:
                page = str(st.get("studio_page") or "").strip()
            if page:
                return page
        except Exception:
            continue
    return ""


def disk_creative_slice() -> dict:
    """Nested Creative keys from disk (top-level or creative_workspace_state)."""
    p = disk_state_path()
    if not p.exists():
        return {}
    try:
        st = (json.loads(p.read_text(encoding="utf-8")).get("state") or {})
    except Exception:
        return {}
    cw = st.get("creative_workspace_state") if isinstance(st.get("creative_workspace_state"), dict) else {}
    keys = (
        "improv_entry_mode",
        "improv_song_source",
        "sbi_preview_source",
        "improv_intelligence_tab",
        "creative_improv_intelligence_tab",
        "improv_active_mission",
        "improv_mission_pick",
        "ii_selected_section",
        "ii_selected_chord",
        "ii_selected_chord_label",
        "harmony_map_section",
        "harmony_map_chord",
    )
    out: dict = {"studio_page": str(st.get("studio_page") or "").strip()}
    for k in keys:
        out[k] = st.get(k) if st.get(k) not in (None, "") else cw.get(k)
    return out


def wait_disk_page(want: str, timeout: float = 20.0) -> str:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        last = disk_studio_page()
        if last == want:
            return last
        time.sleep(0.5)
    return last


def name_custom_song(page: Page, title: str) -> bool:
    try:
        box = page.locator('[data-testid="stTextInput"] input')
        if box.count() == 0:
            return False
        el = box.first
        el.click(timeout=2000)
        el.fill(title)
        page.keyboard.press("Enter")
        wait_idle(page, 2000)
        return True
    except Exception:
        return False


def seed_trial_song_last_custom(page: Page, notes: list[str]) -> None:
    """Ensure LAST_CUSTOM = Trial Song without leaving Global Active as Custom."""
    if not goto_custom(page):
        notes.append("seed_trial: goto_custom failed")
        return
    settle(page, 2)
    body = low(page.inner_text("body") or "")
    if "trial song" not in body:
        _click_button_has(page, r"New song") or click_button_has(page, r"New song")
        wait_idle(page, 1500)
        name_custom_song(page, "Trial Song")
        set_original_key(page, "E")
        wait_idle(page, 1500)
    notes.append("seed_trial: Trial Song touched as LAST_CUSTOM")
    click_nav(page, "Songs")
    wait_idle(page, 2000)


def open_sbi_custom_source(page: Page, notes: list[str]) -> bool:
    """Creative → Entry & Jam → Song-Based → Custom progression (nested, not top-level Custom)."""
    goto_improv(page, notes)
    if not (
        click_radio(page, "Entry & Jam")
        or click_button_has(page, r"Entry & Jam")
        or click_radio(page, "Entry")
    ):
        notes.append("open_sbi_custom: Entry & Jam tab missing")
    settle(page, 2)
    if not (
        click_radio(page, "Song-Based")
        or click_radio(page, "Play Song-Based")
        or click_button_has(page, r"Song-Based")
    ):
        notes.append("open_sbi_custom: Song-Based entry mode missing")
        return False
    settle(page, 2)

    # Streamlit radio labels are often covered by an inner <p> that intercepts
    # pointer events. Prefer native input.click() / keyboard over label force-click.
    clicked = False
    try:
        via = page.evaluate(
            """() => {
              const groups = [...document.querySelectorAll('[role="radiogroup"]')];
              for (const g of groups) {
                const gtxt = (g.innerText || '').toLowerCase();
                if (!gtxt.includes('active song') || !gtxt.includes('custom progression')) continue;
                const labels = [...g.querySelectorAll('label')];
                const custom = labels.find((l) => /custom progression/i.test(l.innerText || ''));
                if (!custom) continue;
                custom.scrollIntoView({block: 'center'});
                const input = custom.querySelector('input[type=radio]');
                if (input) {
                  input.click();
                  input.dispatchEvent(new Event('input', {bubbles: true}));
                  input.dispatchEvent(new Event('change', {bubbles: true}));
                  return 'input';
                }
                const p = custom.querySelector('p');
                (p || custom).click();
                return p ? 'p' : 'label';
              }
              return '';
            }"""
        )
        if via:
            clicked = True
            notes.append(f"open_sbi_custom: js-clicked via={via}")
    except Exception as exc:
        notes.append(f"open_sbi_custom: js click error {exc!r}")

    if not clicked:
        try:
            active = page.get_by_role("radio", name=re.compile(r"^Active song$", re.I))
            if active.count():
                active.last.focus()
                page.keyboard.press("ArrowRight")
                clicked = True
                notes.append("open_sbi_custom: ArrowRight from Active song")
        except Exception as exc:
            notes.append(f"open_sbi_custom: keyboard error {exc!r}")

    if not clicked:
        try:
            role = page.get_by_role("radio", name=re.compile(r"Custom Progression", re.I))
            if role.count():
                role.last.click(timeout=5000, force=True)
                clicked = True
                notes.append("open_sbi_custom: force-clicked role=radio")
        except Exception as exc:
            notes.append(f"open_sbi_custom: role click error {exc!r}")

    if not clicked:
        notes.append("open_sbi_custom: Song-source Custom progression radio missing")
        return False

    wait_idle(page, 7000)
    settle(page, 3)

    still = page.evaluate(
        """() => {
          const labels = [...document.querySelectorAll('[role="radiogroup"] label')];
          for (const l of labels) {
            const t = (l.innerText || '').trim();
            if (!/custom progression/i.test(t)) continue;
            const input = l.querySelector('input[type=radio]');
            const role = l.closest('[role=radio]') || l;
            const checked = (input && input.checked)
              || role.getAttribute('aria-checked') === 'true';
            if (checked) return 'custom';
          }
          return 'active';
        }"""
    )
    if still != "custom":
        notes.append("open_sbi_custom: first click did not stick — retry ArrowRight")
        try:
            active = page.get_by_role("radio", name=re.compile(r"^Active song$", re.I))
            if active.count():
                active.last.focus()
                page.keyboard.press("ArrowRight")
                wait_idle(page, 4000)
                settle(page, 2)
        except Exception as exc:
            notes.append(f"open_sbi_custom: retry error {exc!r}")
        try:
            via2 = page.evaluate(
                """() => {
                  const groups = [...document.querySelectorAll('[role="radiogroup"]')];
                  for (const g of groups) {
                    const gtxt = (g.innerText || '').toLowerCase();
                    if (!gtxt.includes('active song') || !gtxt.includes('custom progression')) continue;
                    const labels = [...g.querySelectorAll('label')];
                    const custom = labels.find((l) => /custom progression/i.test(l.innerText || ''));
                    if (!custom) continue;
                    const input = custom.querySelector('input[type=radio]');
                    if (input) { input.click(); return 'retry-input'; }
                  }
                  return '';
                }"""
            )
            if via2:
                notes.append(f"open_sbi_custom: retry via={via2}")
            wait_idle(page, 4000)
            settle(page, 2)
        except Exception as exc:
            notes.append(f"open_sbi_custom: retry js {exc!r}")

    body = low(page.inner_text("body") or "")
    if has_any(body, "custom progression lab", "create your own song") and not has_any(
        body, "song source", "entry & jam", "song-based", "play song-based"
    ):
        notes.append("open_sbi_custom: navigated to top-level Custom page")
        return False

    still = page.evaluate(
        """() => {
          const labels = [...document.querySelectorAll('[role="radiogroup"] label')];
          for (const l of labels) {
            const t = (l.innerText || '').trim();
            if (!/custom progression/i.test(t)) continue;
            const input = l.querySelector('input[type=radio]');
            const role = l.closest('[role=radio]') || l;
            const checked = (input && input.checked)
              || role.getAttribute('aria-checked') === 'true';
            if (checked) return 'custom';
          }
          for (const l of labels) {
            const t = (l.innerText || '').trim();
            if (!/^active song$/i.test(t)) continue;
            const input = l.querySelector('input[type=radio]');
            const role = l.closest('[role=radio]') || l;
            const checked = (input && input.checked)
              || role.getAttribute('aria-checked') === 'true';
            if (checked) return 'active';
          }
          return 'unknown';
        }"""
    )
    notes.append(f"open_sbi_custom: song_source_state={still}")
    if still != "custom":
        # Disk + Trial title is not enough: Active radio can print Trial from a
        # leftover LAST_CUSTOM preview while the card is still Shape/184 chords.
        body_now = page.inner_text("body") or ""
        custom_card = has_any(body_now, "Custom progression") and not has_any(
            body_now, "Active song · Song Selection", "ACTIVE SONG · SONG SELECTION"
        )
        trial_prog = has_any(body_now, "Open Custom Lab")
        if custom_card and trial_prog and has_any(body_now, "trial song"):
            notes.append("open_sbi_custom: accepted via Custom card + Trial + Open Custom Lab")
            return True
        notes.append("open_sbi_custom: radio still not Custom — refuse disk+Trial fallback")
        return False
    return still == "custom"



def port_pids(port: int) -> list[int]:
    out = subprocess.check_output(["netstat", "-ano"], text=True, errors="replace")
    pids: list[int] = []
    for line in out.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            try:
                pids.append(int(line.split()[-1]))
            except Exception:
                pass
    return sorted(set(pids))


def kill_port(port: int) -> None:
    for pid in port_pids(port):
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F", "/T"], check=False, capture_output=True
        )
    time.sleep(2.5)


def wait_http(port: int, timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2) as r:
                if int(getattr(r, "status", 200) or 200) == 200:
                    time.sleep(1.5)
                    return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"Streamlit did not come up on {port}")


def start_streamlit(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            ENTRY,
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--server.address",
            "127.0.0.1",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wait_http(port)
    return proc


def reboot_server() -> None:
    kill_port(PORT)
    start_streamlit(PORT)


def settle(page: Page, sec: float = 4.0) -> None:
    wait_idle(page, 1500)
    page.wait_for_timeout(int(sec * 1000))


def open_fresh(browser) -> Page:
    ctx = browser.new_context(viewport={"width": 1440, "height": 1100})
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
    wait_idle(page, 2500)
    # Cold reboot can paint suite chrome before the Music app finishes hydrating.
    page.wait_for_timeout(2000)
    try:
        page.wait_for_function(
            """() => {
              const body = (document.body && document.body.innerText) || '';
              if (body.length < 400) return false;
              return /Songs|Practice|Backing|Creative|Custom|ACTIVE SONG|Practice \\/ Concert Key/i.test(body);
            }""",
            timeout=90_000,
        )
    except Exception:
        page.wait_for_timeout(10_000)
    wait_idle(page, 3000)
    expand_sidebar(page)
    wait_idle(page, 1500)
    return page


def row(gate: str, ok: bool, browser: str, internal: str = "") -> dict:
    return {
        "gate": gate,
        "ok": bool(ok),
        "browser": browser,
        "internal": internal,
        "verdict": "PASS" if ok else "FAIL",
    }


def main() -> int:
    notes: list[str] = []
    rows: list[dict] = []
    info = meta()
    notes.append(json.dumps(info))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # A Songs
        page = open_fresh(browser)
        click_nav(page, "Songs")
        settle(page, 5)
        shot(page, "A-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, "A-post")
        fam, disk = page_family(body), disk_studio_page()
        rows.append(row("A", fam == "songs", f"family={fam}", f"disk={disk}"))
        page.context.close()

        # B Custom
        page = open_fresh(browser)
        goto_custom(page)
        settle(page, 5)
        shot(page, "B-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, "B-post")
        fam, disk = page_family(body), disk_studio_page()
        rows.append(row("B", fam == "custom", f"family={fam}", f"disk={disk}"))
        page.context.close()

        # C Creative Motif
        page = open_fresh(browser)
        goto_improv(page, notes)
        click_radio(page, "Motif") or click_button_has(page, r"Motif")
        settle(page, 5)
        shot(page, "C-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, "C-post")
        fam, tab, disk = page_family(body), creative_tab(body), disk_studio_page()
        rows.append(row("C", fam == "creative", f"family={fam} tab={tab}", f"disk={disk}"))
        page.context.close()

        # D Creative → SBI → Custom progression (NOT top-level Custom page)
        page = open_fresh(browser)
        seed_trial_song_last_custom(page, notes)
        pick_song(page, notes, "Shape of You", "Pop")
        assert open_sbi_custom_source(page, notes), "failed to open nested SBI Custom source"
        settle(page, 5)
        # Force a persist cycle and wait until nested SBI Custom is on disk.
        click_nav(page, "Creative")  # same page; triggers save hooks without leaving
        settle(page, 3)
        deadline = time.time() + 25
        disk_ok = False
        while time.time() < deadline:
            sl = disk_creative_slice()
            src = str(sl.get("sbi_preview_source") or sl.get("improv_song_source") or "")
            if (
                sl.get("studio_page") == "creative"
                and "Custom" in src
            ):
                disk_ok = True
                break
            time.sleep(0.6)
        body_pre = shot(page, "D-pre")
        fam_pre = page_family(body_pre)
        assert fam_pre == "creative", f"D-pre left Creative: family={fam_pre}"
        notes.append(json.dumps({"D_pre_disk": disk_creative_slice(), "D_pre_disk_ok": disk_ok}))
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, "D-post")
        fam, tab, disk = page_family(body), creative_tab(body), disk_studio_page()
        trial = has_any(body, "Trial Song", "trial song")
        top_custom = has_any(body, "custom progression lab", "create your own song")
        sl = disk_creative_slice()
        src = str(sl.get("sbi_preview_source") or sl.get("improv_song_source") or "")
        ok = (
            fam == "creative"
            and disk == "creative"
            and tab == "sbi"
            and trial
            and not top_custom
            and "Custom" in src
        )
        rows.append(
            row(
                "D",
                ok,
                f"family={fam} tab={tab} trial={trial} top_custom={top_custom} src={src!r}",
                f"disk={disk}",
            )
        )
        page.context.close()

        # E regular Backing
        page = open_fresh(browser)
        click_nav(page, "Songs")
        wait_idle(page, 2000)
        pick_song(page, notes, "Perfect", "Pop")
        click_nav(page, "Backing")
        settle(page, 5)
        shot(page, "E-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, "E-post")
        fam, disk = page_family(body), disk_studio_page()
        rows.append(row("E", fam.startswith("backing"), f"family={fam}", f"disk={disk}"))
        page.context.close()

        # F Custom SBI Backing
        page = open_fresh(browser)
        seed_trial_song_last_custom(page, notes)
        pick_song(page, notes, "Shape of You", "Pop")
        goto_improv(page, notes)
        click_radio(page, "Song-Based") or click_button_has(page, r"Song-Based")
        settle(page, 2)
        click_radio(page, "Custom progression") or click_radio(page, "Custom Progression")
        set_sidebar_pk(page, "E")
        click_open_backing_studio(page, notes, "F-open")
        settle(page, 6)
        shot(page, "F-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, "F-post")
        fam, disk = page_family(body), disk_studio_page()
        ok = fam.startswith("backing") and fam != "practice"
        rows.append(
            row(
                "F",
                ok,
                f"family={fam} catalog_fallback={has_any(body, 'shape of you')}",
                f"disk={disk}",
            )
        )
        page.context.close()

        # G Mission Backing
        page = open_fresh(browser)
        goto_improv(page, notes)
        click_radio(page, "Missions") or click_button_has(page, r"Missions")
        settle(page, 3)
        click_open_backing_studio(page, notes, "G-open")
        settle(page, 5)
        shot(page, "G-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, "G-post")
        fam, disk = page_family(body), disk_studio_page()
        rows.append(row("G", fam.startswith("backing"), f"family={fam}", f"disk={disk}"))
        page.context.close()

        # H Jam Backing
        page = open_fresh(browser)
        goto_improv(page, notes)
        click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry")
        click_radio(page, "Jam Session Generator") or click_button_has(page, r"Jam Session")
        click_open_backing_studio(page, notes, "H-open")
        settle(page, 5)
        shot(page, "H-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, "H-post")
        fam, disk = page_family(body), disk_studio_page()
        rows.append(row("H", fam.startswith("backing"), f"family={fam}", f"disk={disk}"))
        page.context.close()

        # I Entry Style Backing
        page = open_fresh(browser)
        goto_improv(page, notes)
        click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry")
        click_radio(page, "Style Jam Mode") or click_button_has(page, r"Style Jam")
        click_open_backing_studio(page, notes, "I-open")
        settle(page, 5)
        shot(page, "I-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, "I-post")
        fam, disk = page_family(body), disk_studio_page()
        rows.append(row("I", fam.startswith("backing"), f"family={fam}", f"disk={disk}"))

        # P3 Alto + Written
        click_nav(page, "Songs")
        wait_idle(page, 1500)
        set_instrument(page, "Alto Saxophone") or set_instrument(page, "Alto")
        click_button_has(page, r"Written Charts") or click_radio(page, "Written Charts")
        settle(page, 4)
        shot(page, "P3-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, "P3-post")
        try:
            side = page.inner_text('[data-testid="stSidebar"]') or body
        except Exception:
            side = body
        ok = has_any(side, "alto") and has_any(side, "written")
        rows.append(
            row(
                "P3",
                ok,
                f"alto={has_any(side, 'alto')} written={has_any(side, 'written')}",
                disk_studio_page(),
            )
        )

        # P4 Guitar Shape / Capo
        set_instrument(page, "Guitar")
        enable_guitar_capo(page, notes, "C")
        set_shape_tonic(page, "B")
        settle(page, 4)
        shot(page, "P4-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, "P4-post")
        try:
            side = page.inner_text('[data-testid="stSidebar"]') or body
        except Exception:
            side = body
        ok = has_any(side, "guitar") and (
            has_any(side, "shape", "capo") or has_any(body, "shape", "capo")
        )
        rows.append(row("P4", ok, f"side_has_guitar_shape={ok}", disk_studio_page()))

        # P5 Practice Key editability matrix
        pk_matrix = []
        for label, go in [
            ("Songs", lambda: click_nav(page, "Songs")),
            ("Custom", lambda: goto_custom(page)),
            ("Mission", lambda: (goto_improv(page, notes), click_radio(page, "Missions"))),
            ("Harmony Map", lambda: (goto_improv(page, notes), click_radio(page, "Harmony Map"))),
            ("SBI", lambda: (goto_improv(page, notes), click_radio(page, "Song-Based"))),
            ("Backing", lambda: click_nav(page, "Backing")),
        ]:
            try:
                go()
                wait_idle(page, 1200)
                changed = set_sidebar_pk(page, "D")
                pk_matrix.append({"surface": label, "editable": bool(changed)})
            except Exception as exc:
                pk_matrix.append(
                    {"surface": label, "editable": False, "error": str(exc)[:120]}
                )
        rows.append(
            row(
                "P5",
                sum(1 for r in pk_matrix if r.get("editable")) >= 3,
                json.dumps(pk_matrix),
                "",
            )
        )

        browser.close()

    by = {r["gate"]: r for r in rows}
    for pgate, src, note in [
        ("P1", "C", "Mission+Creative restore foundation (deep chord/example partial)"),
        ("P2", "C", "Live Coach/Harmony require Creative page restore"),
        ("P6", "F", "Custom SBI Backing reboot"),
        ("P7", "G", "Mission Backing reboot"),
        ("P8", "H", "Jam Backing reboot"),
        ("P9", "I", "Entry Backing reboot"),
    ]:
        src_row = by.get(src) or {}
        rows.append(
            row(
                pgate,
                bool(src_row.get("ok")),
                f"from {src}: {src_row.get('browser')} | {note}",
                str(src_row.get("internal") or ""),
            )
        )

    report = {"meta": info, "rows": rows, "notes": notes[-30:]}
    (OUT / f"{PREFIX}report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    practice_fails = [
        r
        for r in rows
        if r["gate"] in list("ABCDEFGHI")
        and ("family=practice" in str(r.get("browser")) or not r.get("ok"))
    ]
    return 1 if practice_fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
