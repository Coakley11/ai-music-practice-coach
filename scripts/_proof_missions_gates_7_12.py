"""Owner-checked Missions gates 7-12 on 8552.

Stops with SETUP_FAIL when a required page/owner/key is missing.
Does not continue after a navigation miss.

Usage:
  python scripts/_proof_missions_gates_7_12.py http://127.0.0.1:8552
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
ICONS = Path(r"C:\Users\danie\Documents\GitHub\AI-Music-Practice-Coach-icons\scripts")
sys.path[:0] = [str(SCRIPTS), str(ROOT), str(ICONS)]

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    expand_pages_nav,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_core_workflows_embargo import (  # noqa: E402
    click_generate_example_once,
    mission_selected_chord,
)
from _walk_custom_practice_key import pk_val  # noqa: E402
from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing  # noqa: E402
from _walk_perfect_sbi_widget_lifecycle import original_key_caption  # noqa: E402
from improvisation_motif import abc_body_measures, abc_measure_beats  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8552"
OUT = SCRIPTS / "evidence-missions-stabilize"
OUT.mkdir(parents=True, exist_ok=True)
RESULT: dict[str, object] = {}
NOTES: list[str] = []
BOUNDARIES: list[dict[str, object]] = []


class SetupFail(Exception):
    def __init__(self, gate: str, field: str, detail: str, snap: dict[str, object]):
        super().__init__(f"{gate} SETUP_FAIL first_incorrect={field} {detail}")
        self.gate = gate
        self.field = field
        self.detail = detail
        self.snap = snap


class GateFail(Exception):
    pass


def log(msg: str) -> None:
    NOTES.append(msg)
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def mark(step: str, ok: bool | None, detail: str = "", **fields: object) -> None:
    status = "PASS" if ok is True else ("SETUP_FAIL" if ok is None else "FAIL")
    RESULT[step] = {"ok": ok, "status": status, "detail": detail, **fields}
    log(f"[{status}] {step} — {detail}")


def git_meta() -> dict[str, str]:
    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "--short", "HEAD"]),
        "url": URL,
    }


def settle(page: Page, sec: float = 2.0) -> None:
    wait_idle(page, int(sec * 1000))


def shot(page: Page, name: str) -> str:
    expand_sidebar(page)
    side = ""
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    main = ""
    try:
        main = page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        main = ""
    body = page.inner_text("body") or ""
    (OUT / f"{name}.txt").write_text(
        f"=== SIDEBAR ===\n{side[:8000]}\n\n=== MAIN ===\n{main[:24000]}\n\n=== BODY ===\n{body[:8000]}",
        encoding="utf-8",
    )
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    return main or body


def key_token(raw: str) -> str:
    t = str(raw or "").replace("♯", "#").replace("♭", "b").strip()
    m = re.search(r"([A-G](?:#|b)?m?)", t)
    return m.group(1) if m else t


def pk_live(page: Page) -> str:
    expand_sidebar(page)
    raw = str(pk_val(page) or "").strip()
    if raw:
        return key_token(raw)
    try:
        body = page.inner_text("body") or ""
    except Exception:
        body = ""
    for pat in (
        r"sidebar_display_key:\s*([A-G][#b]?m?)",
        r"canonical_display_key:\s*([A-G][#b]?m?)",
        r'"raw":\s*"([A-G][#b]?m?)"',
        r"Practice Key:\s*\*?\*?([A-G][#b]?m?)",
    ):
        m = re.search(pat, body.replace("♯", "#").replace("♭", "b"))
        if m:
            return key_token(m.group(1))
    return key_token(original_key_caption(body))


def sidebar_song(side: str) -> str:
    text = side or ""
    m = re.search(r"ACTIVE SONG\s+SONG\s+([^\n]+)", text, flags=re.I)
    if m:
        return m.group(1).strip()
    m = re.search(
        r"^SONG\s+([^\n]+(?:Slow Dancing|Perfect)[^\n]*)$",
        text,
        flags=re.I | re.M,
    )
    if m:
        title = m.group(1).strip()
        if "active_song_title" not in title and "live=" not in title:
            return title
    if "Slow Dancing" in text:
        return "Slow Dancing in a Burning Room"
    if re.search(r"Perfect\s+[—\-]", text) or "Perfect —" in text:
        return "Perfect"
    return ""


def studio_page_of(body: str) -> str:
    for pat in (
        r"studio_page raw:\s*(\w+)",
        r"current_studio_page:\s*(\w+)",
        r"final_studio_page:\s*(\w+)",
    ):
        m = re.search(pat, body or "")
        if m:
            return m.group(1).strip().lower()
    return ""


def backing_source_of(body: str) -> str:
    m = re.search(r"backing_context[^\n]*source['\"]?:\s*['\"]?(\w+)", body or "", flags=re.I)
    if m:
        return m.group(1).strip().lower()
    if "Creative Backing Jam · Mission" in (body or "") or "MISSION BACKING" in (body or ""):
        return "mission"
    if "Return to Mission" in (body or "") and studio_page_of(body) == "backing":
        return "mission"
    return ""


def selected_section(body: str) -> str:
    m = re.search(r"Section:\s*\*?\*?([^*\n]+)", body or "")
    return (m.group(1) if m else "").strip()


def owner_snap(page: Page, *, boundary: str = "") -> dict[str, object]:
    expand_sidebar(page)
    side = ""
    main = ""
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    try:
        main = page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        main = ""
    body = page.inner_text("body") or ""
    song = sidebar_song(side)
    snap = {
        "boundary": boundary,
        "studio_page": studio_page_of(body),
        "tab_missions": bool(
            re.search(r"Chord map by section|Selected Mission Chord|Mission instructions", main)
        ),
        "song": song,
        "orig": key_token(original_key_caption(side or body)),
        "pk": pk_live(page),
        "selected_chord": mission_selected_chord(main or body),
        "section": selected_section(main or body),
        "backing_source": backing_source_of(body),
        "map_em": all(tok in (main or body).replace("♯", "#") for tok in ("Em", "C", "G", "D"))
        and "C#m" not in (main.replace("♯", "#") if "Chord map" in main else ""),
        "return_flag": "🚩 Return to Mission" in body or ("🚩" in body and "Return to Mission" in body),
        "perfect_in_song_slot": bool(re.search(r"^Perfect\b", song or "")),
    }
    if boundary:
        BOUNDARIES.append(dict(snap))
        log(
            f"owner@{boundary} page={snap['studio_page']} song={song!r} "
            f"orig={snap['orig']} pk={snap['pk']} chord={snap['selected_chord']!r} "
            f"sec={snap['section']!r} src={snap['backing_source']}"
        )
    return snap


def require(gate: str, snap: dict[str, object], **expect) -> None:
    for field, want in expect.items():
        got = snap.get(field)
        if callable(want):
            if not want(got):
                raise SetupFail(gate, field, f"got={got!r}", snap)
        elif isinstance(want, (set, tuple, list)):
            if got not in want:
                raise SetupFail(gate, field, f"got={got!r} want={want!r}", snap)
        else:
            if got != want:
                raise SetupFail(gate, field, f"got={got!r} want={want!r}", snap)


def set_pk(page: Page, token: str) -> bool:
    aliases = [token]
    extra = {
        "Em": ["E minor"],
        "Eb": ["Eb major", "D# major"],
        "E": ["E major"],
        "C#m": ["C# minor"],
    }
    aliases.extend(extra.get(token, []))
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    expand_sidebar(page)
    for alias in aliases:
        try:
            combo = page.get_by_role("combobox", name="Practice / Concert Key")
            if combo.count() == 0:
                continue
            combo.first.click(timeout=4000)
            page.wait_for_timeout(400)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(str(alias), delay=30)
            page.wait_for_timeout(400)
            opt = page.locator('[role="option"]').filter(
                has_text=re.compile(rf"^{re.escape(alias)}$", re.I)
            )
            if opt.count() == 0:
                page.keyboard.press("Escape")
                continue
            el = opt.first
            el.scroll_into_view_if_needed()
            el.click(timeout=4000)
            settle(page, 3)
            landed = pk_live(page).lower().replace(" ", "")
            if token.lower().replace(" ", "") in landed or alias.lower().replace(" ", "") in landed:
                return True
            page.keyboard.press("Escape")
        except Exception:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
    return bool(set_baseweb_select(page, "Practice / Concert Key", token))


def open_missions(page: Page) -> bool:
    expand_sidebar(page)
    expand_pages_nav(page)
    if not goto_improv(page, NOTES):
        click_nav(page, "Creative")
        settle(page, 2)
    return ensure_missions_workspace(page, NOTES)


def click_missions_page_backing_jam(page: Page) -> bool:
    """Click the Missions-page Mission Backing control in stMain only.

    Visible label is `🎧 Backing Jam` until an example exists (`▶ Practice in Backing Jam`).
    Never click sidebar Backing Track.
    """
    wait_ready(page)
    main = page.locator('[data-testid="stMain"]')
    patterns = (
        r"Practice in Backing Jam",
        r"Open Mission Backing",
        r"Backing Jam",
    )
    for pat in patterns:
        btn = main.get_by_role("button", name=re.compile(pat, re.I))
        n = btn.count()
        log(f"missions_backing_btn {pat!r} n={n}")
        for i in range(n):
            el = btn.nth(i)
            try:
                if not el.is_visible():
                    continue
                label = (el.inner_text() or "").strip().replace("\n", " ")
                el.scroll_into_view_if_needed(timeout=4000)
                try:
                    el.click(timeout=5000, force=False)
                except Exception:
                    el.click(timeout=5000, force=True)
                settle(page, 4)
                wait_ready(page)
                log(f"missions_backing_clicked {label!r} i={i}")
                return True
            except Exception as exc:
                log(f"missions_backing_btn {pat!r} i={i} err {exc!r}")
    js_ok = page.evaluate(
        """() => {
          const main = document.querySelector('[data-testid="stMain"]');
          if (!main) return false;
          const buttons = [...main.querySelectorAll('button')].filter((b) => {
            const vis = !!(b && b.offsetParent !== null);
            const t = (b.innerText || '').replace(/\\s+/g, ' ').trim();
            return vis && /Backing Jam|Practice in Backing/i.test(t);
          });
          const b = buttons[0];
          if (!b) return false;
          b.scrollIntoView({block: 'center'});
          b.click();
          return (b.innerText || '').trim();
        }"""
    )
    if js_ok:
        settle(page, 4)
        wait_ready(page)
        log(f"missions_backing_js {js_ok!r}")
        return True
    return False


def wait_ready(page: Page) -> None:
    try:
        page.wait_for_function(
            """() => {
              const w = document.querySelector('[data-testid="stStatusWidget"]');
              if (!w) return true;
              return !(w.innerText || '').toLowerCase().includes('running');
            }""",
            timeout=20_000,
        )
    except Exception:
        pass


def click_chord_exact(page: Page, label: str) -> bool:
    wait_ready(page)
    main = page.locator('[data-testid="stMain"]')
    btn = main.get_by_role("button", name=label, exact=True)
    n = btn.count()
    log(f"chord_exact {label!r} n={n}")
    for i in range(min(n, 8)):
        el = btn.nth(i)
        try:
            if not el.is_visible():
                continue
            el.scroll_into_view_if_needed(timeout=4000)
            try:
                el.click(timeout=5000, force=False)
            except Exception:
                el.click(timeout=5000, force=True)
            settle(page, 3)
            wait_ready(page)
            after = mission_selected_chord(page.inner_text('[data-testid="stMain"]') or "")
            log(f"chord_exact {label!r} i={i} selected={after!r}")
            if after.lower() == label.lower():
                return True
        except Exception as exc:
            log(f"chord_exact {label!r} i={i} err {exc!r}")
    js_ok = page.evaluate(
        """(label) => {
          const main = document.querySelector('[data-testid="stMain"]');
          if (!main) return false;
          const buttons = [...main.querySelectorAll('button')].filter((b) => {
            const vis = !!(b && b.offsetParent !== null);
            return vis && (b.innerText || '').trim() === label;
          });
          const b = buttons[0];
          if (!b) return false;
          b.scrollIntoView({block: 'center'});
          b.click();
          return true;
        }""",
        label,
    )
    if js_ok:
        settle(page, 3)
        wait_ready(page)
        after = mission_selected_chord(page.inner_text('[data-testid="stMain"]') or "")
        log(f"chord_exact {label!r} js selected={after!r}")
        if after.lower() == label.lower():
            return True
    return False


def phrase_fields(page: Page) -> dict[str, str]:
    main = page.inner_text('[data-testid="stMain"]') or ""
    notes = ""
    rhythm = ""
    transform = ""
    try:
        live = page.locator("#mission-example-live, [data-mission-example='1']").first
        if live.count():
            notes = str(live.get_attribute("data-notes") or "").strip()
            rhythm = str(live.get_attribute("data-rhythm") or "").strip()
            transform = str(live.get_attribute("data-last-transform") or "").strip()
    except Exception:
        pass
    if not notes:
        m = re.search(r"Notes:\s*`([^`]+)`", main)
        if m:
            notes = m.group(1).strip()
        else:
            m = re.search(
                r"Notes:\s*([A-G](?:[#b]|♯|♭)?(?:\s*[–—\-]\s*[A-G](?:[#b]|♯|♭)?)*)",
                main,
            )
            if m:
                notes = m.group(1).strip()
    if not rhythm:
        m2 = re.search(r"Rhythm:\s*`([^`]+)`", main)
        if m2:
            rhythm = m2.group(1).strip()
        else:
            m2 = re.search(r"Rhythm:\s*([♩♪♬zZ.\s]+)", main)
            if m2:
                rhythm = m2.group(1).strip()
    if not transform:
        try:
            transform = str(
                page.locator("[data-last-transform]").first.get_attribute("data-last-transform") or ""
            )
        except Exception:
            transform = ""
    if not transform:
        m3 = re.search(r'data-last-transform="([^"]*)"', main)
        transform = m3.group(1) if m3 else ""
    abc = ""
    try:
        exp = page.get_by_text("ABC source (optional)", exact=False)
        if exp.count():
            exp.first.click(timeout=4000)
            settle(page, 1)
        codes = page.locator('[data-testid="stMain"] code')
        for i in range(codes.count()):
            txt = str(codes.nth(i).inner_text(timeout=2000) or "")
            if txt.strip().startswith("X:1"):
                abc = txt
                break
    except Exception:
        abc = ""
    return {
        "notes": notes,
        "rhythm": rhythm,
        "transform": transform,
        "abc": abc,
        "has_example": bool(notes)
        and ("Mission example" in main or "Optional example" in main or "Sheet music" in main),
    }


def pitches_of(notes: str) -> list[str]:
    return re.findall(r"[A-G](?:#|b)?", notes.replace("♯", "#").replace("♭", "b"))


def pick_mission(page: Page, label: str) -> bool:
    box = page.locator('[data-testid="stMain"] [data-testid="stSelectbox"]').filter(
        has_text=re.compile(r"Choose a mission", re.I)
    )
    if box.count():
        try:
            clickable = box.first.locator('[data-baseweb="select"], [role="combobox"], input').first
            (clickable if clickable.count() else box.first).click(timeout=4000)
            page.wait_for_timeout(400)
            opt = page.get_by_role("option", name=re.compile(re.escape(label), re.I))
            if opt.count():
                opt.first.click(timeout=4000)
                settle(page, 2)
                wait_ready(page)
                main = page.inner_text('[data-testid="stMain"]') or ""
                if label[:18] in main:
                    log(f"pick_mission ok {label!r}")
                    return True
        except Exception as exc:
            log(f"pick_mission select err {exc!r}")
    ok = set_baseweb_select(page, "Choose a mission", label, prefer_sidebar=False)
    if ok:
        settle(page, 2)
        wait_ready(page)
        log(f"pick_mission baseweb ok {label!r}")
        return True
    log(f"pick_mission failed {label!r}")
    return False


def click_change_rhythm_until_different(page: Page, before_rhythm: str) -> dict[str, object]:
    last = phrase_fields(page)
    for attempt in range(1, 5):
        if not click_button_has(page, r"^Change Rhythm$"):
            return {"clicked": False, "fields": last, "attempt": attempt}
        settle(page, 3)
        wait_ready(page)
        last = phrase_fields(page)
        if str(last.get("rhythm") or "") != str(before_rhythm or "") and last.get("rhythm"):
            return {"clicked": True, "fields": last, "attempt": attempt}
    return {"clicked": True, "fields": last, "attempt": 4}


def setup_slow_dancing_em(page: Page) -> dict[str, object]:
    click_nav(page, "Songs")
    settle(page, 3)
    wait_ready(page)
    landed = pick_song(page, NOTES, "Slow Dancing in a Burning Room", "Pop")
    settle(page, 4)
    wait_ready(page)
    snap_s = owner_snap(page, boundary="songs_slow")
    if "Slow Dancing" not in str(snap_s.get("song") or ""):
        landed = pick_song(page, NOTES, "Slow Dancing in a Burning Room", "Pop") or landed
        settle(page, 5)
        wait_ready(page)
        snap_s = owner_snap(page, boundary="songs_slow_retry")
    if "Slow Dancing" not in str(snap_s.get("song") or ""):
        raise SetupFail("g7", "song", f"Slow Dancing not active after pick landed={landed}", snap_s)
    orig = str(snap_s.get("orig") or "")
    if orig not in {"C#m", "C#"}:
        raise SetupFail("g7", "orig", f"expected C#m got {orig!r}", snap_s)
    if pk_live(page) not in {"Em", "E"}:
        if not set_pk(page, "Em"):
            raise SetupFail("g7", "pk", f"could not set Em, live={pk_live(page)!r}", owner_snap(page))
        settle(page, 3)
    if pk_live(page) not in {"Em", "E"}:
        raise SetupFail("g7", "pk", f"Practice Key not Em after commit live={pk_live(page)!r}", owner_snap(page))
    if not open_missions(page):
        raise SetupFail("g7", "tab_missions", "Missions tab not ready", owner_snap(page))
    settle(page, 4)
    snap = owner_snap(page, boundary="g7_prereq")
    shot(page, "g7-prereq")
    require(
        "g7",
        snap,
        studio_page="creative",
        tab_missions=True,
    )
    if "Slow Dancing" not in str(snap.get("song") or ""):
        raise SetupFail("g7", "song", f"got {snap.get('song')!r}", snap)
    if snap.get("orig") not in {"C#m", "C#"}:
        raise SetupFail("g7", "orig", f"got {snap.get('orig')!r}", snap)
    if snap.get("pk") not in {"Em", "E"}:
        raise SetupFail("g7", "pk", f"got {snap.get('pk')!r}", snap)
    main = page.inner_text('[data-testid="stMain"]') or ""
    text = main.replace("♯", "#")
    if not all(tok in text for tok in ("Em", "G", "D")):
        raise SetupFail("g7", "map_em", "transposed Em map not visible", snap)
    return snap


def main() -> int:
    RESULT["meta"] = git_meta()
    RESULT["boundaries"] = BOUNDARIES
    for g in (
        "g7_chord_tiles",
        "g8_mission_backing",
        "g9_return_to_mission",
        "g10_change_rhythm",
        "g11_four_four_split",
        "g12_perfect_eb_to_e",
    ):
        RESULT[g] = {"ok": None, "status": "NOT_PROVEN", "detail": "not reached"}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.set_default_timeout(25_000)
        try:
            goto = URL if "?dev=" in URL else f"{URL.rstrip('/')}/?dev=1"
            page.goto(goto, wait_until="domcontentloaded", timeout=180_000)
            settle(page, 8)
            wait_ready(page)

            setup_slow_dancing_em(page)
            clicks: list[dict[str, object]] = []
            targets = ["G", "D", "C", "Em"]
            for lab in targets:
                ok_click = click_chord_exact(page, lab)
                snap_c = owner_snap(page, boundary=f"g7_click_{lab}")
                shot(page, f"g7-click-{lab}")
                rec = {
                    "want": lab,
                    "clicked": ok_click,
                    "selected": snap_c.get("selected_chord"),
                    "section": snap_c.get("section"),
                    "song": snap_c.get("song"),
                    "orig": snap_c.get("orig"),
                    "pk": snap_c.get("pk"),
                }
                clicks.append(rec)
                if not ok_click:
                    mark(
                        "g7_chord_tiles",
                        False,
                        f"first_incorrect=selected_chord click {lab} failed {rec}",
                        first_incorrect="selected_chord",
                        clicks=clicks,
                    )
                    raise GateFail()
                if snap_c.get("selected_chord") != lab:
                    mark(
                        "g7_chord_tiles",
                        False,
                        f"first_incorrect=selected_chord got={snap_c.get('selected_chord')!r}",
                        first_incorrect="selected_chord",
                        clicks=clicks,
                    )
                    raise GateFail()
                if "Slow Dancing" not in str(snap_c.get("song") or ""):
                    mark(
                        "g7_chord_tiles",
                        False,
                        "first_incorrect=song",
                        first_incorrect="song",
                        clicks=clicks,
                    )
                    raise GateFail()
                if snap_c.get("orig") not in {"C#m", "C#"}:
                    mark(
                        "g7_chord_tiles",
                        False,
                        f"first_incorrect=orig {snap_c.get('orig')!r}",
                        first_incorrect="orig",
                        clicks=clicks,
                    )
                    raise GateFail()
                if snap_c.get("pk") not in {"Em", "E"}:
                    mark(
                        "g7_chord_tiles",
                        False,
                        f"first_incorrect=pk {snap_c.get('pk')!r}",
                        first_incorrect="pk",
                        clicks=clicks,
                    )
                    raise GateFail()
            mark("g7_chord_tiles", True, f"clicks={clicks}", clicks=clicks)
            last_chord = str(clicks[-1]["selected"])
            last_sec = str(clicks[-1]["section"])

            wait_ready(page)
            opened = click_missions_page_backing_jam(page) or open_mission_backing(page, NOTES)
            settle(page, 5)
            snap_b = owner_snap(page, boundary="g8_mission_backing")
            shot(page, "g8-mission-backing")
            if not opened or snap_b.get("studio_page") != "backing":
                mark(
                    "g8_mission_backing",
                    None,
                    f"SETUP_FAIL first_incorrect=studio_page got={snap_b.get('studio_page')!r} opened={opened}",
                    first_incorrect="studio_page",
                    snap=snap_b,
                )
                raise GateFail()
            if snap_b.get("backing_source") != "mission":
                mark(
                    "g8_mission_backing",
                    False,
                    f"first_incorrect=backing_source got={snap_b.get('backing_source')!r}",
                    first_incorrect="backing_source",
                    snap=snap_b,
                )
                raise GateFail()
            if "Slow Dancing" not in str(snap_b.get("song") or ""):
                mark(
                    "g8_mission_backing",
                    False,
                    f"first_incorrect=song got={snap_b.get('song')!r}",
                    first_incorrect="song",
                    snap=snap_b,
                )
                raise GateFail()
            if snap_b.get("orig") not in {"C#m", "C#"}:
                mark(
                    "g8_mission_backing",
                    False,
                    f"first_incorrect=orig {snap_b.get('orig')!r}",
                    first_incorrect="orig",
                    snap=snap_b,
                )
                raise GateFail()
            if snap_b.get("pk") not in {"Em", "E"}:
                mark(
                    "g8_mission_backing",
                    False,
                    f"first_incorrect=pk {snap_b.get('pk')!r}",
                    first_incorrect="pk",
                    snap=snap_b,
                )
                raise GateFail()
            body_b = page.inner_text("body") or ""
            if "Perfect" in sidebar_song(page.inner_text('[data-testid="stSidebar"]') or ""):
                mark(
                    "g8_mission_backing",
                    False,
                    "first_incorrect=song Perfect leak",
                    first_incorrect="song",
                    snap=snap_b,
                )
                raise GateFail()
            if not snap_b.get("return_flag") and "Return to Mission" not in body_b:
                mark(
                    "g8_mission_backing",
                    False,
                    "first_incorrect=return_flag",
                    first_incorrect="return_flag",
                    snap=snap_b,
                )
                raise GateFail()
            mark(
                "g8_mission_backing",
                True,
                f"page=backing src=mission song={snap_b.get('song')} orig={snap_b.get('orig')} pk={snap_b.get('pk')} chord={snap_b.get('selected_chord')}",
                snap=snap_b,
            )

            if not click_button_has(page, r"Return to Mission"):
                mark(
                    "g9_return_to_mission",
                    None,
                    "SETUP_FAIL first_incorrect=return_click",
                    first_incorrect="return_click",
                )
                raise GateFail()
            settle(page, 5)
            snap_r = owner_snap(page, boundary="g9_return")
            shot(page, "g9-return-missions")
            if snap_r.get("studio_page") != "creative" or not snap_r.get("tab_missions"):
                mark(
                    "g9_return_to_mission",
                    False,
                    f"first_incorrect=studio_page/tab got page={snap_r.get('studio_page')} tab={snap_r.get('tab_missions')}",
                    first_incorrect="studio_page",
                    snap=snap_r,
                )
                raise GateFail()
            if "Slow Dancing" not in str(snap_r.get("song") or ""):
                mark(
                    "g9_return_to_mission",
                    False,
                    f"first_incorrect=song {snap_r.get('song')!r}",
                    first_incorrect="song",
                    snap=snap_r,
                )
                raise GateFail()
            if snap_r.get("orig") not in {"C#m", "C#"}:
                mark(
                    "g9_return_to_mission",
                    False,
                    f"first_incorrect=orig {snap_r.get('orig')!r}",
                    first_incorrect="orig",
                    snap=snap_r,
                )
                raise GateFail()
            if snap_r.get("pk") not in {"Em", "E"}:
                mark(
                    "g9_return_to_mission",
                    False,
                    f"first_incorrect=pk {snap_r.get('pk')!r}",
                    first_incorrect="pk",
                    snap=snap_r,
                )
                raise GateFail()
            if last_chord and snap_r.get("selected_chord") not in {last_chord, last_chord.replace("m", "")}:
                mark(
                    "g9_return_to_mission",
                    False,
                    f"first_incorrect=selected_chord got={snap_r.get('selected_chord')!r} want={last_chord!r}",
                    first_incorrect="selected_chord",
                    snap=snap_r,
                )
                raise GateFail()
            if snap_r.get("perfect_in_song_slot"):
                mark(
                    "g9_return_to_mission",
                    False,
                    "first_incorrect=song Perfect leak",
                    first_incorrect="song",
                    snap=snap_r,
                )
                raise GateFail()
            mark(
                "g9_return_to_mission",
                True,
                f"restored song={snap_r.get('song')} orig={snap_r.get('orig')} pk={snap_r.get('pk')} chord={snap_r.get('selected_chord')} sec={snap_r.get('section')} last={last_chord}/{last_sec}",
                snap=snap_r,
            )

            if not pick_mission(page, "Resolve every phrase on beat 1"):
                mark(
                    "g10_change_rhythm",
                    None,
                    "SETUP_FAIL first_incorrect=mission_pick beat-1",
                    first_incorrect="mission_pick",
                )
                raise GateFail()
            clicked_gen = click_generate_example_once(page)
            if not clicked_gen:
                gen = page.locator('[data-testid="stMain"]').get_by_role(
                    "button", name=re.compile(r"^Generate example$", re.I)
                )
                if gen.count():
                    gen.first.scroll_into_view_if_needed(timeout=4000)
                    gen.first.click(timeout=5000)
                    settle(page, 4)
                    wait_ready(page)
                    clicked_gen = True
            if not clicked_gen:
                mark(
                    "g10_change_rhythm",
                    None,
                    "SETUP_FAIL first_incorrect=generate_example",
                    first_incorrect="generate_example",
                )
                raise GateFail()
            settle(page, 4)
            before = phrase_fields(page)
            shot(page, "g10-before-rhythm")
            if not before.get("has_example") or not pitches_of(str(before.get("notes") or "")) or not str(before.get("rhythm") or "").strip():
                mark(
                    "g10_change_rhythm",
                    None,
                    f"SETUP_FAIL first_incorrect=phrase notes={before.get('notes')!r} rhythm={before.get('rhythm')!r}",
                    first_incorrect="phrase",
                    before=before,
                )
                raise GateFail()
            snap_before_rhythm = owner_snap(page, boundary="g10_before_rhythm")
            rhythm_click = click_change_rhythm_until_different(page, str(before.get("rhythm") or ""))
            after = dict(rhythm_click.get("fields") or {})
            shot(page, "g10-after-rhythm")
            if not rhythm_click.get("clicked"):
                mark(
                    "g10_change_rhythm",
                    None,
                    "SETUP_FAIL first_incorrect=change_rhythm_button",
                    first_incorrect="change_rhythm_button",
                )
                raise GateFail()
            pit_b = pitches_of(str(before.get("notes") or ""))
            pit_a = pitches_of(str(after.get("notes") or ""))
            rhythm_changed = str(after.get("rhythm") or "") != str(before.get("rhythm") or "") and bool(after.get("rhythm"))
            transform_ok = str(after.get("transform") or "") == "change_rhythm"
            pitches_ok = bool(pit_b) and pit_b == pit_a
            snap_after_rhythm = owner_snap(page, boundary="g10_after_rhythm")
            ident_ok = (
                snap_after_rhythm.get("song") == snap_before_rhythm.get("song")
                and snap_after_rhythm.get("orig") == snap_before_rhythm.get("orig")
                and snap_after_rhythm.get("pk") == snap_before_rhythm.get("pk")
                and snap_after_rhythm.get("section") == snap_before_rhythm.get("section")
                and snap_after_rhythm.get("selected_chord") == snap_before_rhythm.get("selected_chord")
            )
            second = click_change_rhythm_until_different(page, str(after.get("rhythm") or ""))
            after2 = dict(second.get("fields") or after)
            shot(page, "g10-after-rhythm-2")
            second_ok = bool(second.get("clicked")) and pitches_of(str(after2.get("notes") or "")) == pit_a
            if not pitches_ok:
                mark(
                    "g10_change_rhythm",
                    False,
                    f"first_incorrect=pitches before={pit_b} after={pit_a}",
                    first_incorrect="pitches",
                    before=before,
                    after=after,
                )
            elif not rhythm_changed:
                mark(
                    "g10_change_rhythm",
                    False,
                    f"first_incorrect=rhythm before={before.get('rhythm')!r} after={after.get('rhythm')!r}",
                    first_incorrect="rhythm",
                    before=before,
                    after=after,
                )
            elif not transform_ok:
                mark(
                    "g10_change_rhythm",
                    False,
                    f"first_incorrect=transform got={after.get('transform')!r}",
                    first_incorrect="transform",
                    before=before,
                    after=after,
                )
            elif not ident_ok:
                mark(
                    "g10_change_rhythm",
                    False,
                    f"first_incorrect=identity after rhythm song={snap_after_rhythm.get('song')} pk={snap_after_rhythm.get('pk')}",
                    first_incorrect="identity",
                    before=before,
                    after=after,
                )
            elif not second_ok:
                mark(
                    "g10_change_rhythm",
                    False,
                    f"first_incorrect=second_change_rhythm notes={after2.get('notes')!r}",
                    first_incorrect="second_change_rhythm",
                    before=before,
                    after=after,
                    after2=after2,
                )
            else:
                mark(
                    "g10_change_rhythm",
                    True,
                    f"pitches={pit_a} rhythm {before.get('rhythm')!r}->{after.get('rhythm')!r}->{after2.get('rhythm')!r} transform={after.get('transform')}",
                    before=before,
                    after=after,
                    after2=after2,
                )

            def _g11_ok(abc_text: str, *, require_five: bool) -> tuple[bool, str, list[float], list[str]]:
                measures = abc_body_measures(abc_text)
                beats = [abc_measure_beats(m) for m in measures if str(m).strip()]
                meter_ok = "M:4/4" in abc_text.replace(" ", "") or "M:4/4" in abc_text
                totals_ok = bool(beats) and abs(beats[0] - 4.0) < 0.08 and all(
                    abs(b - 4.0) < 0.08 for b in beats
                )
                split_ok = len(measures) >= 2 and "|" in abc_text
                if require_five:
                    five_ok = split_ok and totals_ok and meter_ok
                    return five_ok and meter_ok and totals_ok and split_ok, "five_q", beats, measures
                return meter_ok and totals_ok, "after_rhythm", beats, measures

            abc_gen = str(before.get("abc") or "")
            abc_ry = str(after.get("abc") or after2.get("abc") or "")
            if not abc_gen.strip().startswith("X:1"):
                mark(
                    "g11_four_four_split",
                    None,
                    "SETUP_FAIL first_incorrect=abc missing X:1",
                    first_incorrect="abc",
                    abc=abc_gen[:240],
                )
            else:
                gen_ok, _, gen_beats, gen_meas = _g11_ok(abc_gen, require_five=True)
                ry_ok, _, ry_beats, ry_meas = _g11_ok(abc_ry or abc_gen, require_five=False)
                five_q = str(before.get("rhythm") or "").count("♩") >= 5 and len(pit_b) >= 5
                if not five_q:
                    mark(
                        "g11_four_four_split",
                        False,
                        f"first_incorrect=five_quarters notes={pit_b} rhythm={before.get('rhythm')!r}",
                        first_incorrect="five_quarters",
                        abc=abc_gen[:400],
                    )
                elif not gen_ok:
                    mark(
                        "g11_four_four_split",
                        False,
                        f"first_incorrect=generated_measures beats={gen_beats}",
                        first_incorrect="measure_beats",
                        abc=abc_gen[:400],
                        beats=gen_beats,
                        measures=gen_meas,
                    )
                elif abc_ry and not ry_ok:
                    mark(
                        "g11_four_four_split",
                        False,
                        f"first_incorrect=after_rhythm_measures beats={ry_beats}",
                        first_incorrect="after_rhythm_measures",
                        abc=abc_ry[:400],
                        beats=ry_beats,
                    )
                else:
                    mark(
                        "g11_four_four_split",
                        True,
                        f"gen_beats={gen_beats} after_beats={ry_beats} bars={len(gen_meas)} five_q={five_q}",
                        abc=abc_gen[:400],
                        abc_after=(abc_ry or "")[:400],
                        beats=gen_beats,
                        beats_after=ry_beats,
                    )

            click_nav(page, "Songs")
            settle(page, 2)
            pick_song(page, NOTES, "Perfect", "Pop")
            settle(page, 4)
            snap_p = owner_snap(page, boundary="g12_perfect_songs")
            shot(page, "g12-perfect-selected")
            if "Perfect" not in str(snap_p.get("song") or ""):
                raise SetupFail("g12", "song", f"Perfect not active {snap_p.get('song')!r}", snap_p)
            if snap_p.get("orig") not in {"G", "G major"}:
                raise SetupFail("g12", "orig", f"expected G got {snap_p.get('orig')!r}", snap_p)
            if not set_pk(page, "Eb"):
                raise SetupFail("g12", "pk", f"could not set Eb live={pk_live(page)!r}", owner_snap(page))
            settle(page, 3)
            if pk_live(page) not in {"Eb", "D#"}:
                raise SetupFail("g12", "pk", f"Eb did not commit live={pk_live(page)!r}", owner_snap(page))
            if not open_missions(page):
                raise SetupFail("g12", "tab_missions", "Missions not ready", owner_snap(page))
            settle(page, 4)
            snap_m = owner_snap(page, boundary="g12_missions_eb")
            shot(page, "g12-missions-eb")
            if snap_m.get("orig") not in {"G", "G major"} or snap_m.get("pk") not in {"Eb", "D#"}:
                mark(
                    "g12_perfect_eb_to_e",
                    False,
                    f"first_incorrect=missions_eb orig={snap_m.get('orig')} pk={snap_m.get('pk')}",
                    first_incorrect="pk" if snap_m.get("pk") not in {"Eb", "D#"} else "orig",
                    snap=snap_m,
                )
                raise GateFail()
            if not set_pk(page, "E"):
                mark(
                    "g12_perfect_eb_to_e",
                    False,
                    f"first_incorrect=set_E live={pk_live(page)!r}",
                    first_incorrect="pk",
                )
                raise GateFail()
            settle(page, 3)
            snap_e = owner_snap(page, boundary="g12_missions_e")
            shot(page, "g12-missions-e")
            if snap_e.get("pk") not in {"E", "E major"}:
                mark(
                    "g12_perfect_eb_to_e",
                    False,
                    f"first_incorrect=pk after E got={snap_e.get('pk')!r}",
                    first_incorrect="pk",
                    snap=snap_e,
                )
                raise GateFail()
            click_nav(page, "Songs")
            settle(page, 3)
            snap_s1 = owner_snap(page, boundary="g12_songs_e")
            if snap_s1.get("pk") not in {"E", "E major"} or "Perfect" not in str(snap_s1.get("song") or ""):
                mark(
                    "g12_perfect_eb_to_e",
                    False,
                    f"first_incorrect=songs_after_missions pk={snap_s1.get('pk')} song={snap_s1.get('song')}",
                    first_incorrect="pk" if snap_s1.get("pk") not in {"E", "E major"} else "song",
                    snap=snap_s1,
                )
                raise GateFail()
            open_missions(page)
            settle(page, 3)
            snap_m2 = owner_snap(page, boundary="g12_missions_e_return")
            if snap_m2.get("pk") not in {"E", "E major"}:
                mark(
                    "g12_perfect_eb_to_e",
                    False,
                    f"first_incorrect=pk missions return {snap_m2.get('pk')!r}",
                    first_incorrect="pk",
                    snap=snap_m2,
                )
                raise GateFail()
            page.reload(wait_until="domcontentloaded", timeout=180_000)
            settle(page, 5)
            click_nav(page, "Songs")
            settle(page, 3)
            snap_rf = owner_snap(page, boundary="g12_refresh")
            shot(page, "g12-refresh")
            if "Perfect" not in str(snap_rf.get("song") or ""):
                mark(
                    "g12_perfect_eb_to_e",
                    False,
                    f"first_incorrect=song after refresh {snap_rf.get('song')!r}",
                    first_incorrect="song",
                    snap=snap_rf,
                )
                raise GateFail()
            if snap_rf.get("orig") not in {"G", "G major"}:
                mark(
                    "g12_perfect_eb_to_e",
                    False,
                    f"first_incorrect=orig after refresh {snap_rf.get('orig')!r}",
                    first_incorrect="orig",
                    snap=snap_rf,
                )
                raise GateFail()
            if snap_rf.get("pk") not in {"E", "E major"}:
                mark(
                    "g12_perfect_eb_to_e",
                    False,
                    f"first_incorrect=pk after refresh {snap_rf.get('pk')!r}",
                    first_incorrect="pk",
                    snap=snap_rf,
                )
                raise GateFail()
            mark(
                "g12_perfect_eb_to_e",
                True,
                f"orig={snap_rf.get('orig')} pk={snap_rf.get('pk')} song={snap_rf.get('song')}",
                snap=snap_rf,
            )
        except SetupFail as exc:
            shot(page, f"{exc.gate}-setup-fail")
            mark(
                exc.gate,
                None,
                f"SETUP_FAIL first_incorrect={exc.field} {exc.detail}",
                first_incorrect=exc.field,
                snap=exc.snap,
            )
        except GateFail:
            pass
        finally:
            browser.close()

    RESULT["boundaries"] = BOUNDARIES
    (OUT / "gates-7-12-summary.json").write_text(
        json.dumps({"meta": RESULT.get("meta"), "notes": NOTES[-80:], "gates": RESULT}, indent=2),
        encoding="utf-8",
    )
    failed = [
        k
        for k, v in RESULT.items()
        if k not in {"meta", "boundaries"}
        and isinstance(v, dict)
        and v.get("ok") is False
    ]
    setup = [
        k
        for k, v in RESULT.items()
        if k not in {"meta", "boundaries"}
        and isinstance(v, dict)
        and v.get("status") == "SETUP_FAIL"
    ]
    print(f"failed={failed or 'none'} setup_fail={setup or 'none'}", flush=True)
    if failed or setup:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
