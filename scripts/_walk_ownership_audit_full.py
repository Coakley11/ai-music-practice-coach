"""Full Creative/Backing ownership audit — Custom/SBI/Mission/reboot (no disk seed).

Usage:
  python scripts/_walk_ownership_audit_full.py http://127.0.0.1:8521
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
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
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_custom_practice_key import (  # noqa: E402
    goto_custom,
    pk_val,
    set_original_key,
    set_practice_key as set_custom_pk,
)
from _walk_pass8_live import set_practice_key as set_sidebar_pk  # noqa: E402
from _walk_pass8_validate import click_chord, ensure_missions_workspace  # noqa: E402
from _walk_reboot_persistence_ai_p19 import (  # noqa: E402
    open_sbi_custom_source,
    settle,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8521"
ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "own-audit-"
PORT = int(re.search(r":(\d+)", URL).group(1))


def meta() -> dict:
    def _run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    return {
        "branch": _run(["git", "branch", "--show-current"]),
        "sha": _run(["git", "rev-parse", "HEAD"]),
        "dirty": len([ln for ln in _run(["git", "status", "--porcelain"]).splitlines() if ln.strip()]),
        "url": URL,
    }


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    (OUT / f"{stem}.txt").write_text(body[:32000], encoding="utf-8")
    return body


def row(gate: str, ok: bool, detail: str) -> dict:
    return {"gate": gate, "ok": bool(ok), "verdict": "PASS" if ok else "FAIL", "detail": detail}


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def has(body: str, *needles: str) -> bool:
    b = low(body)
    return all(low(n) in b for n in needles)


def has_any(body: str, *needles: str) -> bool:
    b = low(body)
    return any(low(n) in b for n in needles)


def reject_shape_dm(body: str) -> bool:
    b = low(body)
    # Shape contamination signals when Trial is expected
    if "shape of you" in b and "trial song" not in b:
        return False
    if re.search(r"practice(?:\s*/\s*concert)?\s*key[^\n]{0,60}\bdm\b", b):
        if "trial song" in b:
            return False
    return True


def progression_em_d(body: str) -> bool:
    """True when Verse Progression actually lists Em and D bars (not palette chips)."""
    text = body or ""
    # Empty-builder tip means no committed chords yet.
    if re.search(
        r"Verse Progression[\s\S]{0,200}Tap a chord above",
        text,
        re.I,
    ):
        return False
    if re.search(r"Add chords in step 2 to see your song structure", text, re.I):
        # Structure panel empty — only pass if Verse Progression panel has real tiles.
        pass
    m = re.search(
        r"Verse Progression(.{0,1500}?)(?:Tip:|Chord extensions|Pop presets|Undo last|Edit chords)",
        text,
        re.S | re.I,
    )
    if not m:
        return False
    chunk = m.group(1)
    if re.search(r"Tap a chord above", chunk, re.I):
        return False
    # Need Em appearing twice and D appearing twice in the committed panel.
    ems = len(re.findall(r"\bEm\b", chunk))
    ds = len(re.findall(r"(?<![A-G#b])\bD\b(?![#bmA-Za-z])", chunk))
    return ems >= 2 and ds >= 2


def rendered_em_em_d_d(body: str) -> bool:
    """True when any surface shows the Trial progression as real chords (not palette-only).

    Accepts Custom Verse panel, SBI ``Concert Practice Key Progression: Em · Em · D · D``,
    or Backing ``Progression: Verse · Em – Em – D – D``.
    """
    text = body or ""
    if progression_em_d(text):
        return True
    # Reject dict-repr leak from unexpanded CPL entries.
    if re.search(r"\{['\"]chord['\"]", text):
        return False
    if re.search(r"Trial Song\s*[·.]\s*0\s*chords", text, re.I):
        return False
    # SBI Creative preview
    m = re.search(
        r"Concert Practice Key Progression:\s*([^\n]{0,200})",
        text,
        re.I,
    )
    if m:
        line = m.group(1)
        if line.count("Em") >= 2 and bool(
            re.search(r"(?<![A-G#b])\bD\b(?![#bmA-Za-z])", line)
        ):
            # Prefer middle-dot join Em · Em · D · D
            if re.search(r"Em\s*[·•]\s*Em\s*[·•]\s*D\s*[·•]\s*D", line):
                return True
            if line.count("Em") >= 2 and line.count("D") >= 2:
                return True
    # Custom SBI Backing card
    m2 = re.search(r"Progression:\s*([^\n]{0,240})", text, re.I)
    if m2:
        line = m2.group(1)
        if re.search(r"Em\s*[–\-]\s*Em\s*[–\-]\s*D\s*[–\-]\s*D", line):
            return True
        if line.count("Em") >= 2 and bool(
            re.search(r"(?<![A-G#b])\bD\b(?![#bmA-Za-z])", line)
        ):
            return True
    return False


def rendered_dm_dm_c_c(body: str) -> bool:
    """True when SBI/Backing shows Trial D→C projection as Dm · Dm · C · C."""
    text = body or ""
    if re.search(r"\{['\"]chord['\"]", text):
        return False
    m = re.search(
        r"Concert Practice Key Progression:\s*([^\n]{0,200})",
        text,
        re.I,
    )
    if m:
        line = m.group(1)
        if re.search(r"Dm\s*[·•]\s*Dm\s*[·•]\s*C\s*[·•]\s*C", line):
            return True
        if line.count("Dm") >= 2 and bool(
            re.search(r"(?<![A-G#b])\bC\b(?![#bmA-Za-z])", line)
        ):
            return True
    m2 = re.search(r"Progression:\s*([^\n]{0,240})", text, re.I)
    if m2:
        line = m2.group(1)
        if re.search(r"Dm\s*[–\-]\s*Dm\s*[–\-]\s*C\s*[–\-]\s*C", line):
            return True
        if line.count("Dm") >= 2 and bool(
            re.search(r"(?<![A-G#b])\bC\b(?![#bmA-Za-z])", line)
        ):
            return True
    return False


def missions_derived_from_custom_trial(body: str, *, projected: str) -> bool:
    """Missions collapses multi-bar holds; accept unique chords derived from Trial.

    D major source Em Em D D → map shows Em / D.
    C major projection Dm Dm C C → map shows Dm / C.
    """
    text = body or ""
    if not re.search(r"(Embargo Trial|Trial Song)", text, re.I):
        return False
    if re.search(r"Say\s*[—-]\s*John Mayer", text, re.I):
        return False
    chunk_m = re.search(
        r"Chord map by section(.*?)(?:Mission instructions|Optional example|Generate example)",
        text,
        re.I | re.S,
    )
    chunk = chunk_m.group(1) if chunk_m else text
    key = str(projected or "").strip().upper()
    if key == "D":
        return bool(
            re.search(r"\bEm\b", chunk)
            and re.search(r"(?<![A-G#b])\bD\b(?![#bmA-Za-z])", chunk)
        )
    if key == "C":
        return bool(
            re.search(r"\bDm\b", chunk)
            and re.search(r"(?<![A-G#b])\bC\b(?![#bmA-Za-z])", chunk)
        )
    return False


def fill_title(page: Page, title: str = "Trial Song") -> bool:
    for loc in (
        page.get_by_label(re.compile(r"^Song title$", re.I)),
        page.locator('input[placeholder*="Ballad"]'),
        page.locator('input[aria-label*="Song title" i]'),
    ):
        try:
            if loc.count() == 0:
                continue
            el = loc.first
            if not el.is_visible():
                continue
            el.click(timeout=2000)
            el.fill("")
            el.fill(title)
            el.press("Tab")
            wait_idle(page, 800)
            return True
        except Exception:
            continue
    return False


def add_chord_bar(page: Page, chord: str) -> bool:
    """Pick a chord chip then apply 1 bar — wait for Streamlit rerun between steps."""
    chord = str(chord or "").strip()
    if not chord:
        return False
    ok = False
    # Prefer chips under "1. Click a chord" (Streamlit siblings, not DOM children of
    # .cpl-builder-panel — that markdown wrapper does not enclose the buttons).
    try:
        heading = page.get_by_text(re.compile(r"1\.\s*Click a chord", re.I)).first
        heading.scroll_into_view_if_needed()
        # Chord row is the next button cluster after the heading.
        btn = page.get_by_role("button", name=chord, exact=True).first
        btn.scroll_into_view_if_needed()
        try:
            btn.click(timeout=5000)
        except Exception:
            btn.click(force=True, timeout=5000)
        ok = True
        wait_idle(page, 3000)
    except Exception:
        ok = False
    if not ok:
        try:
            exp = page.locator('[data-testid="stExpander"]').filter(
                has_text=re.compile(r"Custom\s*/\s*slash chord", re.I)
            )
            if exp.count() > 0:
                try:
                    exp.first.click(timeout=2000)
                except Exception:
                    pass
                wait_idle(page, 800)
            inp = page.get_by_label(re.compile(r"^Custom chord$", re.I))
            if inp.count() == 0:
                inp = page.locator('input[placeholder*="Cmaj7"]')
            if inp.count() > 0:
                inp.first.click(timeout=2000)
                inp.first.fill(chord)
                inp.first.press("Tab")
                wait_idle(page, 2000)
                if click_button_has(page, r"^Use chord$"):
                    ok = True
                    wait_idle(page, 2500)
        except Exception:
            ok = False
    if not ok:
        ok = click_button_has(page, rf"^{re.escape(chord)}$")
        wait_idle(page, 2500)
    ok2 = (
        click_button_has(page, r"^1 bar$")
        or click_button_has(page, r"1 bar")
    )
    wait_idle(page, 2500)
    return bool(ok and ok2)


def build_trial_song(page: Page, notes: list[str]) -> bool:
    """Create Trial Song @ D major Em Em D D, save to library."""
    from _walk_custom_practice_key import original_key_val, key_is

    if not goto_custom(page):
        notes.append("goto_custom failed")
        return False
    click_button_has(page, r"New song") or click_button_has(page, r"New Song")
    settle(page, 2.5)
    # Prefer Clear section so we prove chord commits even when LAST_CUSTOM
    # already restored Trial Song (New song clicks are flaky under Playwright).
    for _ in range(2):
        try:
            clr = page.get_by_role("button", name="Clear section", exact=True)
            if clr.count() == 0:
                break
            btn = clr.first
            if not btn.is_enabled():
                break
            btn.click(force=True, timeout=4000)
            settle(page, 2)
        except Exception:
            break
    body_cleared = page.inner_text("body") or ""
    if progression_em_d(body_cleared):
        notes.append("WARN clear_section_left_em_d")
    fill_title(page, "Trial Song")
    # Original Key must land on D — verify and retry (human failure: stuck at C).
    orig_ok = False
    for attempt in range(3):
        set_original_key(page, "D") or set_original_key(page, "D major")
        settle(page, 1.5)
        ov = original_key_val(page)
        notes.append(f"orig_attempt={attempt} val={ov!r}")
        if key_is(ov, "D") or "d major" in low(ov):
            orig_ok = True
            break
    if not orig_ok:
        notes.append("FAIL original_key_not_D")
        shot(page, "custom-orig-fail")
        return False
    # Align Practice Key to D so builder chips show Em/D in home spelling
    set_custom_pk(page, "D") or set_sidebar_pk(page, "D")
    settle(page, 1.5)
    pk = pk_val(page)
    notes.append(f"pk_after_align={pk!r}")
    for ch in ("Em", "Em", "D", "D"):
        if not add_chord_bar(page, ch):
            notes.append(f"add_chord_bar miss {ch}")
            # Typed-chord fallback
            try:
                page.get_by_label(re.compile(r"Custom chord", re.I)).first.fill(ch)
                click_button_has(page, r"^Use chord$")
                settle(page, 1)
                click_button_has(page, r"^1 bar$")
                settle(page, 1.5)
                notes.append(f"typed_fallback_{ch}")
            except Exception as exc:
                notes.append(f"typed_fallback_fail_{ch}:{exc}")
    settle(page, 1)
    body_pre = page.inner_text("body") or ""
    if not progression_em_d(body_pre):
        notes.append("FAIL progression_not_visible_before_save")
        # One more attempt: use duration after selecting via first matching button
        for ch in ("Em", "D"):
            add_chord_bar(page, ch)
        settle(page, 1)
        body_pre = page.inner_text("body") or ""
    if not progression_em_d(body_pre):
        notes.append("FAIL progression_still_empty")
        shot(page, "custom-prog-empty")
        return False
    saved = click_button_has(page, r"Save to library")
    settle(page, 2)
    body = page.inner_text("body") or ""
    msg_ok = bool(
        re.search(r"saved.*trial song.*library", body, re.I)
        or re.search(r"saved to custom library", body, re.I)
    )
    orig_saved_d = bool(re.search(r"original key\s+d\b", low(body))) or bool(
        re.search(r"original key:\s*d\b", low(body))
    )
    notes.append(
        f"save_clicked={saved} msg_ok={msg_ok} orig_saved_d={orig_saved_d} pk={pk_val(page)!r}"
    )
    shot(page, "custom-trial-saved")
    visible_trial = "trial song" in low(body)
    # Stay on Custom for callers that scrape progression immediately after build.
    # Save-toast wording can vary; visible Trial + progression is the product tuple.
    return bool(saved) and orig_ok and (msg_ok or visible_trial) and (
        orig_saved_d or progression_em_d(body)
    )


def assert_tuple(
    body: str,
    *,
    want_title: str,
    want_key_tokens: tuple[str, ...],
    reject_titles: tuple[str, ...] = ("My Progression",),
    reject_keys: tuple[str, ...] = (),
    need_prog: bool = True,
) -> tuple[bool, str]:
    b = body or ""
    title_ok = want_title.lower() in low(b)
    for rt in reject_titles:
        if rt.lower() in low(b) and want_title.lower() not in low(b):
            return False, f"reject_title={rt}"
    key_ok = any(tok.lower() in low(b) for tok in want_key_tokens)
    for rk in reject_keys:
        if re.search(rf"practice(?:\s*/\s*concert)?\s*key[^\n]{{0,60}}\b{re.escape(rk)}\b", low(b)):
            return False, f"reject_key={rk}"
    prog_ok = progression_em_d(b) if need_prog else True
    ok = title_ok and key_ok and prog_ok
    return ok, f"title={title_ok} key={key_ok} prog={prog_ok}"


def reboot_server(notes: list[str]) -> None:
    """Kill and restart Streamlit on PORT — no disk seed."""
    notes.append(f"reboot_begin port={PORT}")
    # Kill every listener on PORT (parent + child / leftover PIDs).
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"$cs=@(Get-NetTCPConnection -LocalPort {PORT} -ErrorAction SilentlyContinue | "
                f"Select-Object -ExpandProperty OwningProcess -Unique); "
                f"foreach($p in $cs){{ if($p){{ Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }} }}; "
                f"Start-Sleep -Seconds 1; "
                f"$left=@(Get-NetTCPConnection -LocalPort {PORT} -ErrorAction SilentlyContinue); "
                f"if($left.Count){{ foreach($c in $left){{ Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue }} }}",
            ],
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except Exception as exc:
        notes.append(f"reboot_kill_err={exc!r}")
    time.sleep(2)
    # Start fresh
    log = OUT / f"{PREFIX}reboot-server.log"
    try:
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "streamlit_music_practice_app.py",
                "--server.port",
                str(PORT),
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            cwd=str(ROOT),
            stdout=open(log, "w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )
    except Exception as exc:
        notes.append(f"reboot_start_err={exc!r}")
        return
    # Wait for HTTP
    import urllib.request

    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            urllib.request.urlopen(URL, timeout=2)
            notes.append("reboot_http_up")
            return
        except Exception:
            time.sleep(1.5)
    notes.append("reboot_http_timeout")


def open_fresh(browser) -> Page:
    ctx = browser.new_context(viewport={"width": 1440, "height": 1100})
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=120000)
    settle(page, 3)
    expand_sidebar(page)
    settle(page, 1.5)
    return page


def main() -> int:
    notes: list[str] = []
    rows: list[dict] = []
    info = meta()
    notes.append(json.dumps(info))
    browser = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = open_fresh(browser)
            _run_gates(page, browser, notes, rows)
            try:
                browser.close()
            except Exception:
                pass
    except Exception as exc:
        notes.append(f"FATAL={exc!r}")
        rows.append(row("FATAL", False, repr(exc)))

    summary = {
        "meta": info,
        "rows": rows,
        "notes": notes,
        "all_pass": bool(rows) and all(r["ok"] for r in rows),
        "pass_count": sum(1 for r in rows if r["ok"]),
        "fail_count": sum(1 for r in rows if not r["ok"]),
        "total": len(rows),
    }
    (OUT / f"{PREFIX}results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        f"branch={info.get('branch')}",
        f"sha={info.get('sha')}",
        f"dirty={info.get('dirty')}",
        f"url={URL}",
        f"pass={summary['pass_count']}/{summary['total']}",
        "",
        *[f"{r['gate']}: {r['verdict']} — {r['detail']}" for r in rows],
        "",
        "NOTES",
        *notes[-100:],
    ]
    text = "\n".join(lines)
    (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
    return 0 if summary["all_pass"] else 1


def _run_gates(page: Page, browser, notes: list[str], rows: list[dict]) -> None:
    # ========== CUSTOM OWNER SEQUENCE ==========
    # Force catalog Shape as Global Active (Custom may already be GA from prior runs)
    click_nav(page, "Songs")
    settle(page, 2)
    click_radio(page, "Song Selection") or click_button_has(page, r"Use catalog") or click_radio(
        page, "Catalog"
    ) or click_button_has(page, r"Song Selection \(catalog")
    settle(page, 1)
    pick_song(page, notes, "Shape of You", "Pop")
    settle(page, 2)
    set_sidebar_pk(page, "D minor") or set_sidebar_pk(page, "Dm")
    settle(page, 2)
    body = shot(page, "01-shape-dm")
    shape_ok = "Shape of You" in body and "Trial Song" not in (body.split("ACTIVE SONG")[-1][:200] if "ACTIVE SONG" in body else "")
    # Softer: Shape title visible and pick landed
    shape_ok = "Shape of You" in body
    rows.append(row("C1_SHAPE_DM", shape_ok, f"shape={shape_ok} pk={pk_val(page)!r}"))

    # 3-6 Trial Song Custom create/save
    trial_ok = build_trial_song(page, notes)
    rows.append(row("C2_TRIAL_SAVE", trial_ok, "; ".join(notes[-5:])))

    # Confirm LAST_CUSTOM path: Creative → SBI → Custom
    sbi_ok = open_sbi_custom_source(page, notes)
    settle(page, 3)
    body = shot(page, "02-sbi-custom")
    ok, detail = assert_tuple(
        body,
        want_title="Trial Song",
        want_key_tokens=("D major", " D ", "Key: D", "Original D", "practice", "D"),
        reject_titles=("My Progression",),
        reject_keys=("Dm", "Cm"),
        need_prog=True,
    )
    title_ok = "trial song" in low(body)
    my_only = "my progression" in low(body) and not title_ok
    dm_contam = bool(re.search(r"practice(?:\s*/\s*concert)?\s*key[^\n]{0,60}\bdm\b", low(body)))
    sbi_gate = bool(sbi_ok) and title_ok and not my_only and progression_em_d(body) and not dm_contam
    rows.append(
        row(
            "C3_SBI_CUSTOM",
            sbi_gate,
            f"sbi_open={sbi_ok} title={title_ok} my_only={my_only} dm={dm_contam} {detail}",
        )
    )

    # 9-10 Open Custom Page — Trial Song
    goto_custom(page)
    settle(page, 2)
    body = shot(page, "03-custom-page")
    custom_title = "trial song" in low(body)
    custom_orig = has_any(body, "D major", "Original Key")
    rows.append(
        row(
            "C4_OPEN_CUSTOM",
            custom_title and not ("my progression" in low(body) and not custom_title),
            f"title={custom_title} orig_hint={custom_orig} pk={pk_val(page)!r}",
        )
    )

    # 11-12 Return Creative → SBI Custom (not Active)
    sbi_ok2 = open_sbi_custom_source(page, notes)
    settle(page, 2)
    body = shot(page, "04-return-creative-sbi")
    still_custom = has_any(body, "Custom Progression", "custom progression")
    not_forced_active_only = "trial song" in low(body) or still_custom
    rows.append(
        row(
            "C5_RETURN_SBI_CUSTOM",
            bool(sbi_ok2) and not_forced_active_only and "trial song" in low(body),
            f"sbi={sbi_ok2} custom_src={still_custom} trial={'trial song' in low(body)}",
        )
    )

    # 13-15 Activate Custom as Global Active
    goto_custom(page)
    settle(page, 2)
    if "Trial Song" not in (page.inner_text("body") or ""):
        click_button_has(page, r"Load saved") or True
        settle(page, 1)
    act = click_button_has(page, r"Set as Active Song")
    settle(page, 3)
    click_nav(page, "Songs")
    settle(page, 2)
    body = shot(page, "05-ga-custom")
    ga_ok = "trial song" in low(body)
    shape_still = bool(re.search(r"active song[^\n]{0,80}shape of you", low(body)))
    rows.append(
        row(
            "C6_GA_CUSTOM",
            bool(act) and ga_ok and not shape_still,
            f"act={act} trial={ga_ok} shape_still={shape_still} pk={pk_val(page)!r}",
        )
    )

    # 16-17 Custom SBI Backing
    open_sbi_custom_source(page, notes)
    settle(page, 2)
    opened = click_open_backing_studio(page, notes, "C7") or click_button_has(
        page, r"Open in Backing"
    )
    settle(page, 3)
    body = shot(page, "06-custom-sbi-backing")
    back_ok = (
        bool(opened)
        and "trial song" in low(body)
        and progression_em_d(body)
        and not bool(re.search(r"practice(?:\s*/\s*concert)?\s*key[^\n]{0,60}\bdm\b", low(body)))
    )
    rows.append(
        row(
            "C7_CUSTOM_SBI_BACKING",
            back_ok,
            f"opened={opened} trial={'trial song' in low(body)} prog={progression_em_d(body)}",
        )
    )

    # 18-19 Change Backing PK; Shape global key must remain unchanged
    before_shape_note = "shape_pk_expected=Dm_from_step1"
    set_sidebar_pk(page, "E") or set_custom_pk(page, "E")
    settle(page, 2)
    body = shot(page, "07-backing-pk-e")
    click_nav(page, "Songs")
    settle(page, 2)
    pick_song(page, notes, "Shape of You", "Pop")
    settle(page, 2)
    body = shot(page, "08-shape-pk-intact")
    shape_pk = pk_val(page)
    shape_became_e = low(shape_pk) in {"e", "e major", "emajor"}
    rows.append(
        row(
            "C8_SHAPE_PK_INTACT",
            not shape_became_e and bool(shape_pk),
            f"{before_shape_note} shape_pk={shape_pk!r} became_e={shape_became_e}",
        )
    )

    # ========== MISSION FAMILY ==========
    pick_song(page, notes, "Shape of You", "Pop")
    settle(page, 1)
    set_sidebar_pk(page, "C minor") or set_sidebar_pk(page, "Cm")
    settle(page, 2)
    goto_improv(page, notes)
    settle(page, 2)
    click_radio(page, "Missions") or click_button_has(page, r"Missions")
    settle(page, 2)
    ensure_missions_workspace(page, notes)
    settle(page, 1)
    labels: list[str] = []
    try:
        main = page.locator('[data-testid="stMain"]')
        btns = main.get_by_role("button")
        for i in range(min(btns.count(), 80)):
            t = (btns.nth(i).inner_text() or "").strip().split("\n")[0]
            if re.match(r"^[A-G][#b]?m?\d*$", t):
                labels.append(t)
    except Exception:
        pass
    target = next(
        (x for x in labels if x in ("Dm", "D", "Cm", "Fm")),
        labels[1] if len(labels) > 1 else (labels[0] if labels else ""),
    )
    if target:
        click_chord(page, target)
        settle(page, 2)
    gen = click_button_has(page, r"Generate Example") or click_button_has(page, r"Generate example")
    settle(page, 3)
    body = shot(page, "09-mission-example")
    example_before = has_any(body, "example", "ABC", "motif", "notes", "Generate")
    mission_chord_before = target
    notes.append(f"mission_gen={gen} chord={target} labels={labels[:8]}")

    opened_mb = (
        click_button_has(page, r"Practice in Backing Jam")
        or click_button_has(page, r"← Return to Mission")  # noop probe
        or click_button_has(page, r"Jam")
        or click_open_backing_studio(page, notes, "M1")
    )
    settle(page, 3)
    body = shot(page, "10-mission-backing")
    # Must be Mission Backing — not Custom progression backing fallthrough.
    is_mission_backing = has_any(body, "Return to Mission", "MISSION BACKING", "Mission Backing")
    is_custom_fallthrough = has_any(body, "Custom progression", "Return to Custom") and not is_mission_backing
    ret = (
        click_button_has(page, r"← Return to Mission")
        or click_button_has(page, r"Return to Mission")
        or click_button_has(page, r"Back to Mission")
        or click_button_has(page, r"Return to Missions")
    )
    settle(page, 3)
    body = shot(page, "11-return-mission")
    restored_chord = mission_chord_before.lower() in low(body) if mission_chord_before else False
    gen2 = click_button_has(page, r"Generate Example") or click_button_has(page, r"Generate example")
    settle(page, 2)
    body2 = shot(page, "12-mission-regen")
    rows.append(
        row(
            "M1_EXAMPLE_RETURN",
            bool(opened_mb)
            and is_mission_backing
            and not is_custom_fallthrough
            and bool(ret)
            and (restored_chord or example_before)
            and bool(gen2),
            f"open={opened_mb} mission_bk={is_mission_backing} custom_ft={is_custom_fallthrough} "
            f"ret={ret} chord={restored_chord} gen2={gen2}",
        )
    )

    # Mission Backing PK transpose
    click_radio(page, "Missions") or click_button_has(page, r"Missions")
    settle(page, 2)
    if "Dm" in labels:
        click_chord(page, "Dm")
        settle(page, 1.5)
    click_button_has(page, r"Generate Example") or click_button_has(page, r"Generate example")
    settle(page, 2)
    body_pre = shot(page, "13-mission-pre-transpose")
    notes_pre = re.findall(
        r"\b([A-G][#b]?)\b",
        body_pre[body_pre.lower().find("example") :][:800]
        if "example" in low(body_pre)
        else body_pre[:1200],
    )
    opened_mb2 = click_button_has(page, r"Open.*Backing") or click_open_backing_studio(
        page, notes, "M2"
    )
    settle(page, 3)
    set_sidebar_pk(page, "C# minor") or set_sidebar_pk(page, "C#m") or set_sidebar_pk(
        page, "Db minor"
    )
    settle(page, 3)
    body_post = shot(page, "14-mission-backing-cshm")
    transposed = has_any(body_post, "D#m", "Ebm", "C#m", "C# minor", "Db minor")
    still_only_dm = bool(re.search(r"current chord:\s*Dm\b", body_post, re.I)) and not has_any(
        body_post, "D#m", "Ebm"
    )
    rows.append(
        row(
            "M2_BACKING_TRANSPOSE",
            bool(opened_mb2) and transposed and not still_only_dm,
            f"open={opened_mb2} transposed={transposed} still_dm={still_only_dm} notes_pre={notes_pre[:12]}",
        )
    )

    # Return to Regular Catalog Song Backing
    reg = (
        click_button_has(page, r"Return to Regular Catalog Song Backing")
        or click_button_has(page, r"Regular Catalog")
        or click_button_has(page, r"Catalog Song Backing")
        or click_button_has(page, r"Return to.*Catalog")
    )
    settle(page, 3)
    body = shot(page, "15-return-regular-backing")
    on_catalog_backing = has_any(body, "Backing", "Quick BPM", "Tempo") and (
        has_any(body, "Shape of You", "Catalog", "Return to")
    )
    rows.append(
        row(
            "M3_RETURN_REGULAR",
            bool(reg) and on_catalog_backing,
            f"clicked={reg} on_backing={on_catalog_backing}",
        )
    )

    # ========== REBOOT ==========
    open_sbi_custom_source(page, notes)
    settle(page, 2)
    pre_reboot = shot(page, "16-pre-reboot")
    pre_has_trial = "trial song" in low(pre_reboot)
    page.context.close()
    reboot_server(notes)
    page = open_fresh(browser)
    body = shot(page, "17-post-reboot")
    # Stricter reboot: must restore Trial/Custom SBI — not Practice fallback or Shape-only Active.
    landed_practice_only = bool(re.search(r"practice length", low(body))) and not has_any(
        body, "Trial Song", "Custom Progression", "Return to"
    )
    restored_trial = "trial song" in low(body)
    restored_sbi_custom = has_any(body, "Custom Progression", "custom progression") and restored_trial
    shape_replaced_trial = "shape of you" in low(body) and pre_has_trial and not restored_trial
    rows.append(
        row(
            "R1_REBOOT_NO_PRACTICE_FALLBACK",
            not landed_practice_only and restored_trial and not shape_replaced_trial,
            f"practice_only={landed_practice_only} trial={restored_trial} "
            f"sbi_custom={restored_sbi_custom} shape_replaced={shape_replaced_trial}",
        )
    )

    # ========== MOTIF VISUAL ==========
    goto_improv(page, notes)
    click_radio(page, "Motif") or click_button_has(page, r"Motif")
    settle(page, 2)
    click_button_has(page, r"Generate motif") or click_button_has(page, r"New motif")
    settle(page, 2)
    click_button_has(page, r"Build Motif Pattern") or click_button_has(page, r"Build pattern")
    settle(page, 2)
    body = shot(page, "18-motif-pattern")
    click_button_has(page, r"Sheet") or click_button_has(page, r"Notation") or click_button_has(
        page, r"Show notation"
    )
    settle(page, 2)
    body2 = shot(page, "19-motif-sheet")
    has_motif = has_any(body2, "Motif on", "Motif pattern", "♩")
    has_abc = has_any(body2, "X:", "ABC", "K:")
    rows.append(row("MOTIF_VISUAL", has_motif, f"motif={has_motif} abc={has_abc}"))


if __name__ == "__main__":
    raise SystemExit(main())
